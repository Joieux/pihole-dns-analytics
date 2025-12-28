# Pi-hole DNS Analytics - Raspberry Pi Zero 2W Installation Guide

Complete setup guide optimized for the Pi Zero 2W's 512MB RAM and 1GHz single-core CPU.

## Why Pi Zero 2W?

The Pi Zero 2W is perfect for this project:
- **Low power**: ~0.5W idle, ~1.5W under load
- **Compact**: Perfect for discreet network placement
- **WiFi built-in**: No need for dongles
- **Cost effective**: ~$15 hardware
- **Silent**: No fans needed
- **24/7 capable**: Designed for always-on operation

## Hardware Requirements

### Essential
- Raspberry Pi Zero 2W
- 8GB+ microSD card (Class 10 or UHS-1)
- 2.5A USB-C power supply
- microSD card reader

### Optional but Recommended
- Case with heatsink
- USB Ethernet adapter (for wired connection)
- HDMI mini adapter (for initial setup)

## Software Requirements

- Raspberry Pi OS Lite (64-bit) - **IMPORTANT: Use Lite version**
- Python 3.9+
- Pi-hole 5.x

## Step-by-Step Installation

### 1. Prepare Raspberry Pi OS

**Use Raspberry Pi Imager:**

1. Download Raspberry Pi Imager: https://www.raspberrypi.com/software/
2. Insert microSD card
3. Choose OS: **Raspberry Pi OS Lite (64-bit)**
4. Configure settings (⚙️ icon):
   - Enable SSH
   - Set username/password
   - Configure WiFi
   - Set hostname (e.g., `pihole-zero`)
5. Write to SD card

**Why Lite?** The Lite version uses ~100MB less RAM than Desktop, critical for Pi Zero 2W.

### 2. Initial System Setup

Boot your Pi Zero 2W and SSH in:

```bash
ssh pi@pihole-zero.local
```

Update system:
```bash
sudo apt update
sudo apt upgrade -y
```

**Configure for low memory:**
```bash
# Reduce GPU memory (we don't need it)
echo "gpu_mem=16" | sudo tee -a /boot/config.txt

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable hciuart

# Reboot
sudo reboot
```

### 3. Install Pi-hole

```bash
curl -sSL https://install.pi-hole.net | bash
```

**Installation tips for Pi Zero 2W:**
- Choose lighttpd (not Apache) for web server
- Select minimal blocking lists initially (you can add more later)
- Note your admin password!

**Post-install optimization:**
```bash
# Reduce Pi-hole log verbosity to save writes
echo "log-queries" | sudo tee -a /etc/dnsmasq.d/02-custom.conf
echo "log-facility=/var/log/pihole.log" | sudo tee -a /etc/dnsmasq.d/02-custom.conf

sudo systemctl restart pihole-FTL
```

### 4. Install Python Dependencies

```bash
# Install Python and pip
sudo apt install -y python3-pip python3-yaml python3-flask

# Install required packages with minimal dependencies
pip3 install --user --no-cache-dir pyyaml==6.0.1
pip3 install --user --no-cache-dir flask==3.0.0

# SQLite is already included in Python
```

**Why `--no-cache-dir`?** Saves ~50MB of disk space.

### 5. Download and Setup Project

```bash
# Create project directory
mkdir -p ~/pihole-analytics
cd ~/pihole-analytics

# Create directory structure
mkdir -p {scripts,app/templates,data,config}

# Download optimized scripts
# (Upload the Pi Zero 2W optimized versions: dns_parser_pizero.py, dashboard_pizero.py, etc.)
```

Copy these files to your Pi:
- `scripts/dns_parser_pizero.py` → `~/pihole-analytics/scripts/dns_parser.py`
- `app/dashboard_pizero.py` → `~/pihole-analytics/app/dashboard.py`
- `app/templates/index_pizero.html` → `~/pihole-analytics/app/templates/index.html`
- `scripts/init_db.py` → `~/pihole-analytics/scripts/init_db.py`
- `config/config.yaml` → `~/pihole-analytics/config/config.yaml`

### 6. Configure Database

Update `config/config.yaml` for Pi Zero 2W:

```yaml
pihole:
  log_path: /var/log/pihole.log

database:
  path: /home/pi/pihole-analytics/data/dns_logs.db
  retention_days: 30  # Reduced from 90 for space

dashboard:
  port: 5000
  host: 0.0.0.0
```

Initialize database:
```bash
cd ~/pihole-analytics
python3 scripts/init_db.py
```

### 7. Create Systemd Services

**DNS Parser Service:**

Create `/etc/systemd/system/dns-parser.service`:
```ini
[Unit]
Description=Pi-hole DNS Log Parser (Pi Zero 2W)
After=pihole-FTL.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pihole-analytics
ExecStart=/usr/bin/python3 /home/pi/pihole-analytics/scripts/dns_parser.py
Restart=always
RestartSec=10

# Pi Zero 2W resource limits
MemoryMax=100M
CPUQuota=50%
Nice=10

[Install]
WantedBy=multi-user.target
```

**Dashboard Service:**

Create `/etc/systemd/system/dns-dashboard.service`:
```ini
[Unit]
Description=Pi-hole DNS Dashboard (Pi Zero 2W)
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pihole-analytics
ExecStart=/usr/bin/python3 /home/pi/pihole-analytics/app/dashboard.py
Restart=always
RestartSec=10

# Pi Zero 2W resource limits
MemoryMax=80M
CPUQuota=30%
Nice=15

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dns-parser dns-dashboard
sudo systemctl start dns-parser dns-dashboard
```

### 8. Verify Installation

Check service status:
```bash
sudo systemctl status dns-parser
sudo systemctl status dns-dashboard
```

View logs:
```bash
journalctl -u dns-parser -f
journalctl -u dns-dashboard -f
```

Access dashboard:
```
http://pihole-zero.local:5000
```

## Performance Tuning for Pi Zero 2W

### SD Card Optimizations

Reduce unnecessary writes:
```bash
# Disable swap (optional, but saves writes)
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo systemctl disable dphys-swapfile

# Mount /tmp to RAM
echo "tmpfs /tmp tmpfs defaults,noatime,size=50M 0 0" | sudo tee -a /etc/fstab
```

### Log Rotation

Configure aggressive log rotation:
```bash
sudo nano /etc/logrotate.d/pihole-analytics
```

Add:
```
/home/pi/pihole-analytics/data/*.log {
    daily
    rotate 3
    compress
    delaycompress
    notifempty
    missingok
}
```

### Database Maintenance

Add weekly vacuum to crontab:
```bash
crontab -e
```

Add:
```
0 3 * * 0 sqlite3 /home/pi/pihole-analytics/data/dns_logs.db 'VACUUM;'
```

## Monitoring Performance

Check memory usage:
```bash
free -h
```

Check CPU usage:
```bash
htop
```

Check service memory:
```bash
sudo systemctl status dns-parser | grep Memory
sudo systemctl status dns-dashboard | grep Memory
```

## Expected Performance Metrics

On Pi Zero 2W:
- **Memory Usage**: ~150MB total (all services)
- **CPU Usage**: 10-30% average
- **Queries Handled**: 2,000-3,000/hour
- **Dashboard Response**: <500ms
- **Database Size**: ~1GB per million queries

## Troubleshooting

### "Out of Memory" Errors

1. Check swap is disabled: `sudo swapon --show`
2. Reduce batch sizes in `dns_parser.py`:
   ```python
   BATCH_SIZE = 25  # Reduced from 50
   BUFFER_MAX = 50  # Reduced from 100
   ```

### Slow Dashboard

1. Increase cache timeout in `dashboard_pizero.py`:
   ```python
   CACHE_TIMEOUT = 30  # Increased from 10
   ```
2. Reduce recent queries:
   ```python
   MAX_RECENT_QUERIES = 25  # Reduced from 50
   ```

### High CPU Usage

1. Increase poll interval in `dns_parser.py`:
   ```python
   POLL_INTERVAL = 1.0  # Increased from 0.5
   ```
2. Check for runaway processes: `htop`

### Database Locks

Pi Zero 2W can struggle with concurrent writes:
```bash
# Increase batch interval
BATCH_INTERVAL = 60  # Increased from 30
```

## Network Configuration

### Static IP (Recommended)

Edit `/etc/dhcpcd.conf`:
```bash
interface wlan0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=127.0.0.1
```

### Configure Clients

Point devices to your Pi Zero 2W:
- Primary DNS: `192.168.1.50` (your Pi's IP)
- Secondary DNS: `1.1.1.1` (fallback)

Or configure at router level for whole network.

## Maintenance Schedule

**Daily** (automatic):
- Log rotation
- Database writes

**Weekly**:
- Check service status
- Review blocked domains
- Database vacuum (automatic Sunday 3am)

**Monthly**:
- Update Pi-hole: `pihole -up`
- Update blocklists: `pihole -g`
- Check SD card health: `sudo badblocks -sv /dev/mmcblk0`

## Backup Strategy

Backup script (`~/backup.sh`):
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
tar czf ~/backups/pihole-backup-$DATE.tar.gz \
    ~/pihole-analytics/data/ \
    ~/pihole-analytics/config/ \
    /etc/pihole/

# Keep only last 7 backups
cd ~/backups && ls -t | tail -n +8 | xargs rm -f
```

Add to crontab:
```bash
0 2 * * * ~/backup.sh
```

## Power Consumption

The Pi Zero 2W draws:
- Idle: ~0.4W
- Average load: ~1.2W
- Peak: ~2.0W

**Annual cost** (at $0.12/kWh): ~$1.26

## Security Considerations

1. **Change default password**: `passwd`
2. **Enable firewall**:
   ```bash
   sudo apt install ufw
   sudo ufw allow 22/tcp  # SSH
   sudo ufw allow 53/tcp  # DNS
   sudo ufw allow 53/udp  # DNS
   sudo ufw allow 80/tcp  # Pi-hole web
   sudo ufw allow 5000/tcp  # Dashboard
   sudo ufw enable
   ```
3. **Keep updated**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

## Further Optimization

### Disable IPv6 (if not needed)
```bash
echo "net.ipv6.conf.all.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Overclock (optional, not recommended)
Only if you have good cooling:
```bash
# Add to /boot/config.txt
over_voltage=2
arm_freq=1200
```

⚠️ **Warning**: Overclocking increases power draw and heat. Not recommended without a heatsink.

## Support

If you encounter issues:
1. Check logs: `journalctl -u dns-parser -n 50`
2. Verify Pi-hole is working: `pihole status`
3. Test dashboard: `curl http://localhost:5000/health`

## Next Steps

- Add custom blocklists
- Configure alerts
- Set up remote access (VPN)
- Add more analytics
- Export to Grafana

Your Pi Zero 2W is now a powerful network monitoring tool! 🎉
