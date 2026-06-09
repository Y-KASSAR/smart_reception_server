from facenet_pytorch import InceptionResnetV1, MTCNN
print("Loading InceptionResnetV1 (vggface2)...")
m = InceptionResnetV1(pretrained="vggface2").eval()
print("Loading MTCNN...")
n = MTCNN()
print("OK")
