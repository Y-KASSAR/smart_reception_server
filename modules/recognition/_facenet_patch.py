"""
Runtime monkey-patch for ``facenet_pytorch.models.utils.detect_face.detect_face``.

Fixes an off-by-N bug in stages 2 and 3 of the cascaded MTCNN detector.
The original loops conditionally skip boxes with invalid pad bounds when
building ``im_data``, but do NOT apply the same filter to ``boxes`` and
``image_inds``. When even one box has invalid bounds, the downstream
``score > threshold`` mask is shorter than ``boxes``, and
``boxes[ipass, :4]`` raises::

    IndexError: The shape of the mask [N-K] at index 0 does not match
    the shape of the indexed tensor [N, 4] at index 0

We replace ``detect_face`` with a corrected copy that tracks the valid
indices and applies them to ``boxes`` / ``image_inds`` before inference.
"""
from __future__ import annotations

from config.logging_config import get_logger

logger = get_logger(__name__)
_PATCHED = False


def apply() -> bool:
    """Install the patched ``detect_face``. Idempotent. Returns True on success."""
    global _PATCHED
    if _PATCHED:
        return True
    try:
        from facenet_pytorch.models.utils import detect_face as _df_module
        from facenet_pytorch.models import mtcnn as _mtcnn_module
        # Build the patched function (closed over the original helpers)
        patched = _build_patched_detect_face(_df_module)
        _df_module.detect_face = patched
        # The MTCNN class imports detect_face at module load time, so patch
        # that reference too.
        _mtcnn_module.detect_face = patched
        _PATCHED = True
        logger.info("facenet_pytorch.detect_face monkey-patched (off-by-N fix)")
        return True
    except Exception as e:
        logger.warning(f"detect_face patch could not be applied: {e}")
        return False


def _build_patched_detect_face(_df_module):
    """Construct the patched function. Keeps the original helpers in scope."""
    import torch
    import numpy as np

    imresample = _df_module.imresample
    generateBoundingBox = _df_module.generateBoundingBox
    bbreg = _df_module.bbreg
    rerec = _df_module.rerec
    pad = _df_module.pad
    fixed_batch_process = _df_module.fixed_batch_process
    batched_nms_numpy = _df_module.batched_nms_numpy
    from torchvision.ops.boxes import batched_nms

    def detect_face(imgs, minsize, pnet, rnet, onet, threshold, factor, device):
        # ---- Identical input handling to the original ------------------------
        if isinstance(imgs, (np.ndarray, torch.Tensor)):
            if isinstance(imgs, np.ndarray):
                imgs = torch.as_tensor(imgs.copy(), device=device)
            if isinstance(imgs, torch.Tensor):
                imgs = torch.as_tensor(imgs, device=device)
            if len(imgs.shape) == 3:
                imgs = imgs.unsqueeze(0)
        else:
            if not isinstance(imgs, (list, tuple)):
                imgs = [imgs]
            if any(img.size != imgs[0].size for img in imgs):
                raise Exception("MTCNN batch processing only compatible with equal-dimension images.")
            imgs = np.stack([np.uint8(img) for img in imgs])
            imgs = torch.as_tensor(imgs.copy(), device=device)

        model_dtype = next(pnet.parameters()).dtype
        imgs = imgs.permute(0, 3, 1, 2).type(model_dtype)

        batch_size = len(imgs)
        h, w = imgs.shape[2:4]
        m = 12.0 / minsize
        minl = min(h, w)
        minl = minl * m

        # ---- First-stage scale pyramid + NMS — unchanged --------------------
        scales = []
        scale_i = m
        while minl >= 12:
            scales.append(scale_i)
            scale_i = scale_i * factor
            minl = minl * factor

        boxes = []
        image_inds = []
        scale_picks = []
        offset = 0
        for scale in scales:
            im_data = imresample(imgs, (int(h * scale + 1), int(w * scale + 1)))
            im_data = (im_data - 127.5) * 0.0078125
            reg, probs = pnet(im_data)
            boxes_scale, image_inds_scale = generateBoundingBox(reg, probs[:, 1], scale, threshold[0])
            boxes.append(boxes_scale)
            image_inds.append(image_inds_scale)
            pick = batched_nms(boxes_scale[:, :4], boxes_scale[:, 4], image_inds_scale, 0.5)
            scale_picks.append(pick + offset)
            offset += boxes_scale.shape[0]

        boxes = torch.cat(boxes, dim=0)
        image_inds = torch.cat(image_inds, dim=0)
        scale_picks = torch.cat(scale_picks, dim=0)

        boxes, image_inds = boxes[scale_picks], image_inds[scale_picks]
        pick = batched_nms(boxes[:, :4], boxes[:, 4], image_inds, 0.7)
        boxes, image_inds = boxes[pick], image_inds[pick]

        regw = boxes[:, 2] - boxes[:, 0]
        regh = boxes[:, 3] - boxes[:, 1]
        qq1 = boxes[:, 0] + boxes[:, 5] * regw
        qq2 = boxes[:, 1] + boxes[:, 6] * regh
        qq3 = boxes[:, 2] + boxes[:, 7] * regw
        qq4 = boxes[:, 3] + boxes[:, 8] * regh
        boxes = torch.stack([qq1, qq2, qq3, qq4, boxes[:, 4]]).permute(1, 0)
        boxes = rerec(boxes)
        y, ey, x, ex = pad(boxes, w, h)

        # ---- Second stage — PATCHED ------------------------------------------
        if len(boxes) > 0:
            im_data = []
            valid_idx = []
            for k in range(len(y)):
                if ey[k] > (y[k] - 1) and ex[k] > (x[k] - 1):
                    img_k = imgs[image_inds[k], :, (y[k] - 1):ey[k], (x[k] - 1):ex[k]].unsqueeze(0)
                    im_data.append(imresample(img_k, (24, 24)))
                    valid_idx.append(k)

            # *** FIX *** filter boxes/image_inds to the same valid indices BEFORE inference
            if not valid_idx:
                boxes = boxes.new_zeros((0, 4))
                image_inds = image_inds.new_zeros((0,), dtype=image_inds.dtype)
            else:
                if len(valid_idx) != len(boxes):
                    idx_t = torch.as_tensor(valid_idx, device=boxes.device, dtype=torch.long)
                    boxes = boxes[idx_t]
                    image_inds = image_inds[idx_t]

                im_data = torch.cat(im_data, dim=0)
                im_data = (im_data - 127.5) * 0.0078125
                out = fixed_batch_process(im_data, rnet)
                out0 = out[0].permute(1, 0)
                out1 = out[1].permute(1, 0)
                score = out1[1, :]
                ipass = score > threshold[1]
                boxes = torch.cat((boxes[ipass, :4], score[ipass].unsqueeze(1)), dim=1)
                image_inds = image_inds[ipass]
                mv = out0[:, ipass].permute(1, 0)

                pick = batched_nms(boxes[:, :4], boxes[:, 4], image_inds, 0.7)
                boxes, image_inds, mv = boxes[pick], image_inds[pick], mv[pick]
                boxes = bbreg(boxes, mv)
                boxes = rerec(boxes)

        # ---- Third stage — PATCHED -------------------------------------------
        points = torch.zeros(0, 5, 2, device=device)
        if len(boxes) > 0:
            y, ey, x, ex = pad(boxes, w, h)
            im_data = []
            valid_idx = []
            for k in range(len(y)):
                if ey[k] > (y[k] - 1) and ex[k] > (x[k] - 1):
                    img_k = imgs[image_inds[k], :, (y[k] - 1):ey[k], (x[k] - 1):ex[k]].unsqueeze(0)
                    im_data.append(imresample(img_k, (48, 48)))
                    valid_idx.append(k)

            if not valid_idx:
                boxes = boxes.new_zeros((0, 5))
                image_inds = image_inds.new_zeros((0,), dtype=image_inds.dtype)
            else:
                if len(valid_idx) != len(boxes):
                    idx_t = torch.as_tensor(valid_idx, device=boxes.device, dtype=torch.long)
                    boxes = boxes[idx_t]
                    image_inds = image_inds[idx_t]

                im_data = torch.cat(im_data, dim=0)
                im_data = (im_data - 127.5) * 0.0078125
                out = fixed_batch_process(im_data, onet)

                out0 = out[0].permute(1, 0)
                out1 = out[1].permute(1, 0)
                out2 = out[2].permute(1, 0)
                score = out2[1, :]
                points = out1
                ipass = score > threshold[2]
                points = points[:, ipass]
                boxes = torch.cat((boxes[ipass, :4], score[ipass].unsqueeze(1)), dim=1)
                image_inds = image_inds[ipass]
                mv = out0[:, ipass].permute(1, 0)

                w_i = boxes[:, 2] - boxes[:, 0] + 1
                h_i = boxes[:, 3] - boxes[:, 1] + 1
                points_x = w_i.repeat(5, 1) * points[:5, :] + boxes[:, 0].repeat(5, 1) - 1
                points_y = h_i.repeat(5, 1) * points[5:10, :] + boxes[:, 1].repeat(5, 1) - 1
                points = torch.stack((points_x, points_y)).permute(2, 1, 0)
                boxes = bbreg(boxes, mv)

                pick = batched_nms_numpy(boxes[:, :4], boxes[:, 4], image_inds, 0.7, 'Min')
                boxes, image_inds, points = boxes[pick], image_inds[pick], points[pick]

        boxes = boxes.cpu().numpy()
        points = points.cpu().numpy()
        image_inds = image_inds.cpu()

        batch_boxes = []
        batch_points = []
        for b_i in range(batch_size):
            b_i_inds = np.where(image_inds == b_i)
            batch_boxes.append(boxes[b_i_inds].copy())
            batch_points.append(points[b_i_inds].copy())

        batch_boxes, batch_points = np.array(batch_boxes, dtype=object), np.array(batch_points, dtype=object)
        return batch_boxes, batch_points

    return detect_face
