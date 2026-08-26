# Pig Tracking Project - Client Setup Guide

Welcome to the Pig Tracking Project! Because this project involves heavy machine learning models and large image datasets, the setup process is split into two parts: cloning the source code from GitHub, and downloading the heavy model/data files separately.

Follow this step-by-step guide to get the project running on your PC.

---

## 1. Prerequisites
Before you begin, ensure you have the following installed on your PC:
* **[Git](https://git-scm.com/downloads)** (To clone the repository)
* **[Python 3.9 - 3.11](https://www.python.org/downloads/)** (Ensure you check the box that says **"Add Python to PATH"** during installation)

---

## 2. Clone the Repository
Open your terminal (Command Prompt or PowerShell) and run the following commands to download the source code:

```bash
# Clone the repository to your local machine
git clone https://github.com/byrondumaya-cmyk/Pig-Tracking.git

# Navigate into the project folder
cd Pig-Tracking
```

---

## 3. Set Up the Python Environment
It is highly recommended to use a virtual environment so the project dependencies do not interfere with other Python software on your PC.

```bash
# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment (Windows)
venv\Scripts\activate

# (If you are on macOS/Linux, run this instead: source venv/bin/activate)
```
*Note: Once activated, you should see `(venv)` at the start of your terminal line.*

---

## 4. Install Dependencies
With the virtual environment activated, install all the required Python libraries:

```bash
# To install the requirements for the Raspberry Pi / Production environment:
pip install -r requirements-pi.txt

# OR, if you plan to do model training on this PC:
pip install -r requirements-train.txt
```

---

## 5. Download the Models & Datasets (Important!)
Because AI models (`.pt` files) and training datasets are extremely large, they are **not** included in the GitHub repository. You must download them separately from the secure storage link provided by the developer.

1. **Download the provided `.zip` file** containing the models and datasets from the developer's Google Drive / Cloud Storage.
2. **Extract the files** into your `Pig-Tracking` folder so that your folder structure looks like this:

```text
Pig-Tracking/
│
├── data/                  <-- (Place the extracted datasets here)
│   ├── train/
│   ├── valid/
│   └── test/
│
├── yolov8n.pt             <-- (Place the base model in the root folder)
├── best.pt                <-- (Place the custom trained model in the root folder)
│
├── src/                   (Already included via GitHub)
├── config/                (Already included via GitHub)
└── README.md              (Already included via GitHub)
```

---

## 6. Run the Application
Once the code is cloned, dependencies are installed, and the heavy files are placed in their correct folders, you are ready to run the system!

Make sure your virtual environment is still active, then run the application (for example, the dashboard):

```bash
python src/main.py
```

If you encounter any issues, please reach out for technical support!
