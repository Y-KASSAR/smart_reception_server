# Raspberry Pi Edge Device — Deployment Guide

This guide walks you through setting up the Raspberry Pi 4 (8 GB) as the
**camera + PIR edge node** that streams JPEG frames to the laptop AI server
running [edge/edge_client.py](../edge/edge_client.py).

> **Architecture reminder.** Per the SDD, the Pi only captures and ships
> frames. All heavy ML (YOLO + MTCNN + FaceNet) runs on the laptop. The Pi
> does **not** install torch / ultralytics / facenet-pytorch — only OpenCV,
> NumPy, requests, and RPi.GPIO.

---

## What you need before you start

| Item | Notes |
|---|---|
| Raspberry Pi 4 (8 GB) | Yours |
| microSD ≥ 32 GB | Class 10 / A2 preferred |
| USB-C 5.1 V / 3 A power supply | Official RPi PSU recommended |
| USB webcam (UVC-compatible 1080p) | Plugs into any USB-3 port on the Pi |
| HC-SR501 PIR motion sensor | 3 jumper wires (F-F) |
| Ethernet cable | Reliability > Wi-Fi for streaming |
| Laptop AI server already running | This repo, server on port 5000 |

---

## 1 — Flash Raspberry Pi OS (on your laptop)

1. Download **Raspberry Pi Imager**: https://www.raspberrypi.com/software/
2. Insert your microSD into the laptop.
3. In Imager:
   - **Choose Device** → Raspberry Pi 4
   - **Choose OS** → *Raspberry Pi OS (64-bit) — Bookworm*
   - **Choose Storage** → your microSD
4. Click ⚙ **Edit Settings** (or press `Ctrl + Shift + X`):
   - **Hostname:** `smart-reception`
   - **Set username and password:** `pi` / *your-strong-password*
   - **Configure wireless LAN:** *(optional — Ethernet is better)*
   - **Set locale settings:** your timezone
   - **Services tab → Enable SSH** → *Use password authentication*
5. **Write**. Takes ~5 minutes.
6. Eject microSD, insert into Pi, plug in power. Wait ~90 s for first boot.

---

## 2 — Find the Pi and SSH in (from your laptop)

```powershell
# On Windows PowerShell — find it on the LAN
arp -a | findstr "b8-27-eb 28-cd-c1 dc-a6-32 e4-5f-01"
# or check your router's DHCP client list for hostname "smart-reception"

ssh pi@smart-reception.local
# or  ssh pi@<the-IP-you-found>
```

If `.local` resolution fails on Windows, install Apple Bonjour (comes with iTunes)
or just use the IP directly.

---

## 3 — Set a static IP (recommended)

```bash
sudo nano /etc/dhcpcd.conf
```

Append (adjust to your network):

```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

```bash
sudo reboot
# wait ~30 s, then reconnect:
ssh pi@192.168.1.100
```

---

## 4 — Connect the hardware

### USB webcam
Plug into any USB-3 port (blue inside). Verify:

```bash
ls /dev/video*       # should show /dev/video0 at minimum
sudo apt install -y v4l-utils fswebcam
v4l2-ctl --list-devices
fswebcam -r 1920x1080 ~/test_capture.jpg

# Copy back to your laptop to view it:
# (from your laptop, in PowerShell)
scp pi@192.168.1.100:~/test_capture.jpg .
```

Open `test_capture.jpg` — you should see whatever the camera was pointed at.

### PIR sensor (HC-SR501)

Pin wiring on the Pi (uses BCM 17 = physical pin 11):

| HC-SR501 pin | Pi physical pin | Pi function |
|---|---|---|
| **VCC** | 2 | 5 V |
| **GND** | 6 | Ground |
| **OUT** | 11 | GPIO 17 (BCM) |

Use F-F jumper wires. **Do not** wire OUT to 5 V — only to GPIO 17.

Quick PIR sanity check:

```bash
sudo apt install -y python3-rpi.gpio
python3 - <<'PY'
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM); GPIO.setup(17, GPIO.IN)
print("Wave at the sensor...")
for _ in range(60):
    print("HIGH" if GPIO.input(17) else "low", end=" ", flush=True)
    time.sleep(0.5)
GPIO.cleanup()
PY
```

You should see `low low ... HIGH HIGH HIGH ... low` when you move in front of it.

---

## 5 — Install Python deps on the Pi

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev libatlas-base-dev

mkdir -p ~/smart_reception && cd ~/smart_reception
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install opencv-python-headless==4.10.0.84 numpy==1.26.4 \
            requests==2.32.3 RPi.GPIO
```

> `opencv-python-headless` is mandatory on the Pi (no GUI dependencies =
> smaller install, no X11 conflicts).

---

## 6 — Copy `edge_client.py` to the Pi

From **your laptop**:

```powershell
# in PowerShell, at the repo root
scp .\edge\edge_client.py pi@192.168.1.100:~/smart_reception/edge_client.py
```

---

## 7 — Configure the edge client

On the Pi, create the env file:

```bash
cat > ~/smart_reception/.env <<'ENV'
SERVER_URL=http://192.168.1.50:5000
API_KEY=replace-with-the-API_KEY-from-your-laptop-.env
CAMERA_ID=lobby_main
DEVICE_ID=0
PIR_PIN=17
FPS=15
HEARTBEAT_INTERVAL_S=30
ENV
```

**SERVER_URL** must be your **laptop's** IP on the LAN. On the laptop run:

```powershell
ipconfig | findstr IPv4
```

…and substitute that value above. `API_KEY` must match exactly what's in
the laptop's `.env` file (project root).

---

## 8 — One-shot manual test (before installing the service)

On the laptop (in the repo dir):

```powershell
.\venv\Scripts\python.exe server_app.py
```

You should see `Application started` and uvicorn on port 5000.

On the Pi:

```bash
cd ~/smart_reception
source venv/bin/activate
set -a; source .env; set +a
python edge_client.py
```

Walk in front of the camera. On the **laptop** logs you should see:

```
INFO  ...api.routes.edge ingest_frame - frame processed: persons=1 faces=1 ...
INFO  ...modules.recognition.face_recognizer - ...
```

If you've enrolled yourself (Day 5 dashboard), the laptop log will also show
`broadcast_guest_identified` events. Hit **Ctrl-C** on both sides to stop.

---

## 9 — Install as systemd service (auto-start on boot)

On the Pi:

```bash
sudo tee /etc/systemd/system/smart-reception-edge.service > /dev/null <<'UNIT'
[Unit]
Description=Smart Reception Edge Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/smart_reception
EnvironmentFile=/home/pi/smart_reception/.env
ExecStart=/home/pi/smart_reception/venv/bin/python edge_client.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now smart-reception-edge
sudo systemctl status smart-reception-edge        # should be active (running)
sudo journalctl -u smart-reception-edge -f        # follow live logs
```

Reboot the Pi (`sudo reboot`) and verify the service comes back up:

```bash
ssh pi@192.168.1.100
sudo systemctl status smart-reception-edge
```

---

## 10 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `VideoCapture: failed to open device 0` | Camera not plugged in or wrong device ID | `ls /dev/video*` then set `DEVICE_ID` accordingly |
| `MotionDetector: GPIO unavailable` warning | `RPi.GPIO` not installed in the venv | `source venv/bin/activate && pip install RPi.GPIO` |
| `upload_frame attempt N failed: Connection refused` | Laptop server not running OR wrong `SERVER_URL` | Check `ipconfig` on the laptop, ping it from the Pi |
| 401 Unauthorized on every frame | `API_KEY` mismatch between Pi `.env` and laptop `.env` | Copy the exact value across; restart both services |
| FPS far below 15 | USB-2 port, bad cable, or large JPEGs | Use a USB-3 port, lower `FPS` to 10 in `.env` |
| `ImportError: numpy.core.multiarray` | Apt's old numpy conflicting with pip's | `pip uninstall numpy && pip install numpy==1.26.4` |
| Service won't start after reboot | Network not up yet | Already handled by `After=network-online.target`; if still flaky, add `RestartSec=15` |

---

## 11 — Sanity checklist before Day 4

- [ ] `sudo systemctl status smart-reception-edge` → **active (running)**
- [ ] Laptop log shows `ingest_frame: persons=N` whenever something moves in front of the camera
- [ ] PIR triggers the camera ("you walk by → frames spike → idle → no frames")
- [ ] `curl -H "X-API-Key: $API_KEY" http://192.168.1.50:5000/api/edge/heartbeat` on the Pi returns `{"status":"ok",...}`
- [ ] `curl http://192.168.1.50:5000/api/system/status` (with a JWT) shows
      `database.ok = true, recognition.detail = "backend=facenet..." or "backend=none, install facenet-pytorch"`

Once those check out, you're ready for the React dashboard (Day 4).
