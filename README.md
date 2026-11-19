Well this is my first vibe coded app ever many bugs will be there but i am happy with i learnt the way to do it
# 🐾 PawHelp - Stray Animal Rescue Network

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Kivy Framework](https://img.shields.io/badge/framework-Kivy%202.3.0-orange.svg)](https://kivy.org/)
[![Android APK](https://img.shields.io/badge/platform-Android%20%7C%20Windows%20%7C%20Linux-brightgreen.svg)]()
[![MySQL 8.0](https://img.shields.io/badge/database-MySQL%208.0-blue.svg)](https://www.mysql.com/)
[![Build APK Workflow](https://github.com/actions/workflows/build-apk.yml/badge.svg)]()

> **"Every stray deserves a helping hand."**  
> PawHelp is a cross-platform mobile and desktop application crafted with Python and Kivy that empowers citizens to quickly report injured, sick, or trapped animals and connects them directly with rescuers.

---

## 📱 Features

- **📍 Instant Geolocation & Location Search**:
  - Auto-detects current GPS/IP location with reverse-geocoding (OpenStreetMap Nominatim) to automatically fetch area names and coordinates.
  - Interactive popup to search any neighborhood or select popular Bengaluru locations (Rajajinagar, Indiranagar, Koramangala, etc.).
  - Instant Google Maps links generated for rescue workers.

- **📝 Rapid Animal Incident Reporting**:
  - Categorized chips for animal types (*Dog*, *Cat*, *Bird*, *Other*).
  - Categorized chips for emergencies (*Injured*, *Sick*, *Trapped*, *Abandoned*, *Other*).
  - Text description of the situation.
  - Photo attachment support with in-app preview.

- **🗄️ MySQL Workbench 8.0 Integration & Offline Resilience**:
  - Full persistence to MySQL Workbench 8.0 via `mysql-connector-python`.
  - Built-in offline fallback: saves to local cache (`reports.json`) if MySQL server is unreachable, and automatically syncs to MySQL upon reconnection.

- **📋 My Reports Screen**:
  - Live dossier of all submitted rescue incidents retrieved directly from MySQL.
  - Incident ID badges, timestamps, status indicators, and direct `[View on Google Maps]` button.
  - Streamlined single top navigation button.

- **📞 Emergency Rescue Directory**:
  - Instant-dial rescue helpline (`+91 74119 96630`).
  - Verified animal shelter directory with services offered.

---

## 🚀 Getting Started (VS Code / Desktop)

### 1. Prerequisites
- Python 3.10 or newer
- MySQL Server & MySQL Workbench 8.0 (optional for local offline mode)

### 2. Installation
Clone this repository and set up a virtual environment:

```bash
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
cd Pawhelp

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# Install dependencies:
pip install -r requirements.txt
```

### 3. Database Setup (MySQL Workbench 8.0)
1. Open **MySQL Workbench 8.0** and connect to your local MySQL instance.
2. Open [`schema.sql`](schema.sql) in Workbench and execute the script to create the database:
   ```sql
   CREATE DATABASE IF NOT EXISTS pawhelp_db;
   USE pawhelp_db;

   CREATE TABLE IF NOT EXISTS reports (
       id INT AUTO_INCREMENT PRIMARY KEY,
       animal_type VARCHAR(64) NOT NULL,
       problem VARCHAR(64) NOT NULL,
       description TEXT,
       location VARCHAR(255) NOT NULL,
       latitude DECIMAL(10, 7) DEFAULT NULL,
       longitude DECIMAL(10, 7) DEFAULT NULL,
       maps_url VARCHAR(500) DEFAULT NULL,
       photo_path VARCHAR(500) DEFAULT NULL,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```
3. Check [`db_config.json`](db_config.json) to match your local MySQL credentials:
   ```json
   {
     "host": "localhost",
     "port": 3306,
     "user": "root",
     "password": "YOUR_MYSQL_PASSWORD",
     "database": "pawhelp_db"
   }
   ```

### 4. Run the Application
```bash
python main.py
```

---

## 🤖 Android APK Conversion & Download

PawHelp is configured with **Buildozer** and an automated **GitHub Actions CI/CD pipeline** to compile Android APKs automatically in the cloud.

### Option A: Download from GitHub Actions (Recommended)
1. Navigate to the **Actions** tab in this GitHub repository.
2. Select the latest **Build Android APK** workflow run.
3. Under **Artifacts**, download the `PawHelp-debug-apk.zip`.
4. Extract the `.apk` file and transfer/install it on any Android device!

### Option B: Build APK Locally (Linux / WSL / Ubuntu)
If you have Ubuntu or Windows Subsystem for Linux (WSL) installed:

```bash
# 1. Install prerequisites
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libffi-dev libssl-dev

# 2. Install Buildozer & Cython
pip install --upgrade buildozer cython virtualenv

# 3. Build APK
buildozer android debug
```
The compiled APK will be output to the `bin/` directory.

---

## 📂 Project Structure

```text
Pawhelp/
├── .github/
│   └── workflows/
│       └── build-apk.yml     # Automated cloud APK builder on Ubuntu
├── .gitignore                # Excludes venv, pycache, and build binaries
├── buildozer.spec            # Android APK packaging specification
├── db_config.json            # MySQL connection configuration
├── main.py                   # Main Kivy application & screen manager
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
└── schema.sql                # MySQL Workbench database schema
```

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
