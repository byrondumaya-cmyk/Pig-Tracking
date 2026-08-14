import os
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_doc(filename, title, sections):
    doc = Document()
    
    # Title
    heading = doc.add_heading(title, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    for section in sections:
        if section['type'] == 'heading':
            doc.add_heading(section['text'], level=section.get('level', 1))
        elif section['type'] == 'paragraph':
            doc.add_paragraph(section['text'])
        elif section['type'] == 'list':
            for item in section['items']:
                doc.add_paragraph(item, style='List Bullet')
        elif section['type'] == 'image':
            if os.path.exists(section['path']):
                try:
                    doc.add_picture(section['path'], width=Inches(6.0))
                    if 'caption' in section:
                        p = doc.add_paragraph(section['caption'])
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        p.runs[0].font.italic = True
                        p.runs[0].font.size = Pt(9)
                except Exception as e:
                    doc.add_paragraph(f"[Image failed to load: {section['path']} - {e}]")
            else:
                doc.add_paragraph(f"[Image not found at: {section['path']}]")
    
    doc.save(filename)
    print(f"Created {filename}")

def main():
    output_dir = os.path.join(os.getcwd(), 'docx_documentation')
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. general_comprehensive_overview.docx
    create_doc(
        os.path.join(output_dir, 'general_comprehensive_overview.docx'),
        'General Comprehensive Overview: Offline AI Swine Health Monitoring System',
        [
            {'type': 'heading', 'text': '1. Executive Summary', 'level': 1},
            {'type': 'paragraph', 'text': 'The Offline AI Swine Health Monitoring System is an edge-AI capstone project designed to run entirely on a Raspberry Pi 4B without requiring cloud connectivity or internet access. It leverages computer vision and thermal sensing to monitor pig behaviors and detect early signs of illness or heat stress.'},
            {'type': 'heading', 'text': '2. Core Features', 'level': 1},
            {'type': 'list', 'items': [
                'Real-time Behavior Detection: Uses a YOLOv8n model optimized with ONNX Runtime to identify 8 pig behaviors.',
                'Thermal Monitoring: Maps temperatures using an Adafruit AMG8833 thermal camera onto bounding boxes.',
                'Heat Stress Awareness: A DHT22 sensor tracks ambient temperature and humidity to calculate the Temperature Humidity Index (THI).',
                'Hybrid Risk Engine: Employs both individual (fever + lethargy) and herd-level (population lethargy) anomaly detection.',
                'Offline Dashboard: A local Flask dashboard accessible over LAN or standalone AP mode.',
                'SMS Alerts: A GSM900A module sends critical text message alerts to farmers instantly.'
            ]},
            {'type': 'heading', 'text': '3. Architecture', 'level': 1},
            {'type': 'paragraph', 'text': 'The system follows a modular, offline-first architecture. It combines asynchronous camera capture, SORT tracking, thermal mapping, and SQLite for data persistence.'}
        ]
    )

    # 2. comprehensive_code_explanation.docx
    create_doc(
        os.path.join(output_dir, 'comprehensive_code_explanation.docx'),
        'Comprehensive Code Explanation',
        [
            {'type': 'heading', 'text': '1. Introduction', 'level': 1},
            {'type': 'paragraph', 'text': 'The system is written in Python 3.11 and structured into several distinct modules.'},
            {'type': 'heading', 'text': '2. Inference & Tracking', 'level': 1},
            {'type': 'paragraph', 'text': 'src/inference/detector.py: Wraps the ONNX runtime session for YOLOv8n inference, managing preprocessing and post-processing (NMS).'},
            {'type': 'paragraph', 'text': 'src/tracking/sort_tracker.py & pig_tracker.py: Implements Simple Online and Realtime Tracking (SORT) using Kalman filters to assign consistent IDs to detected pigs.'},
            {'type': 'heading', 'text': '3. Hardware Interfacing', 'level': 1},
            {'type': 'paragraph', 'text': 'src/hardware/async_camera.py: Implements a non-blocking background thread to capture video frames, improving FPS.'},
            {'type': 'paragraph', 'text': 'src/thermal/thermal_reader.py: Interfaces with the AMG8833 over I2C to retrieve 8x8 temperature grids, scaling them up for visualization.'},
            {'type': 'heading', 'text': '4. Health Risk Engine', 'level': 1},
            {'type': 'paragraph', 'text': 'src/health/risk_engine.py: Evaluates both Individual (Channel 1) and Population (Channel 2) risks using adaptive thresholds based on ambient THI.'},
            {'type': 'heading', 'text': '5. Dashboard', 'level': 1},
            {'type': 'paragraph', 'text': 'src/dashboard/: Uses Flask to serve a local web interface. routes.py provides API endpoints, while stream.py provides the MJPEG video feed.'}
        ]
    )

    # 3. formulas_and_weights_explanation.docx
    create_doc(
        os.path.join(output_dir, 'formulas_and_weights_explanation.docx'),
        'Formulas and Weights Explanation',
        [
            {'type': 'heading', 'text': '1. Temperature Humidity Index (THI)', 'level': 1},
            {'type': 'paragraph', 'text': 'The THI is used to determine ambient heat stress. The formula used is:'},
            {'type': 'paragraph', 'text': 'THI = (1.8 * T + 32) - ((0.55 - 0.0055 * RH) * (1.8 * T - 26))'},
            {'type': 'paragraph', 'text': 'Where T is Temperature in Celsius and RH is Relative Humidity in percentage.'},
            {'type': 'heading', 'text': '2. Hybrid Risk Engine Logic', 'level': 1},
            {'type': 'list', 'items': [
                'Channel 1 (Individual): IF (Stationary >= 15 min) AND (Zone Temp > Ambient + 2.0C) -> Alert.',
                'Channel 2 (Population): IF (Stationary Pigs / Total Pigs >= 0.60) for 3 consecutive seconds -> Alert.',
                'THI Adaptive Threshold: IF (THI > 78), the stationary timer threshold increases from 15 min to 30 min.'
            ]}
        ]
    )

    # 4. goal_of_research_overview.docx
    create_doc(
        os.path.join(output_dir, 'goal_of_research_overview.docx'),
        'Goal of Research Overview',
        [
            {'type': 'heading', 'text': '1. Research Motivation', 'level': 1},
            {'type': 'paragraph', 'text': 'The primary goal is to provide a low-cost, offline, and reliable edge AI solution for swine farmers. Early detection of illness (fever + lethargy) and heat stress is critical for animal welfare and farm productivity.'},
            {'type': 'heading', 'text': '2. Objectives', 'level': 1},
            {'type': 'list', 'items': [
                'Achieve high accuracy (mAP50 >= 0.70) in detecting 8 specific pig behaviors.',
                'Run entirely offline on edge hardware (Raspberry Pi 4B) without recurring cloud computing costs.',
                'Provide actionable SMS alerts immediately when anomalies are detected.',
                'Maintain a local database for historical analysis.'
            ]}
        ]
    )

    # 5. wiring_diagram_comprehensive_explanation.docx
    create_doc(
        os.path.join(output_dir, 'wiring_diagram_comprehensive_explanation.docx'),
        'Wiring Diagram & Comprehensive Explanation',
        [
            {'type': 'heading', 'text': '1. Overview', 'level': 1},
            {'type': 'paragraph', 'text': 'The system relies on a Raspberry Pi 4B connected to a USB Camera, AMG8833 Thermal Sensor, DHT22 Sensor, and GSM900A module.'},
            {'type': 'heading', 'text': '2. AMG8833 Thermal Camera (I2C)', 'level': 1},
            {'type': 'list', 'items': [
                'VIN to Pi 3.3V (Pin 1)',
                'GND to Pi GND (Pin 6)',
                'SDA to Pi GPIO2/SDA1 (Pin 3)',
                'SCL to Pi GPIO3/SCL1 (Pin 5)'
            ]},
            {'type': 'heading', 'text': '3. DHT22 Ambient Sensor (GPIO)', 'level': 1},
            {'type': 'list', 'items': [
                'VCC to Pi 3.3V or 5V',
                'GND to Pi GND',
                'DATA to Pi GPIO4 (Pin 7) (requires 10k pull-up resistor to VCC)'
            ]},
            {'type': 'heading', 'text': '4. GSM900A Module (UART)', 'level': 1},
            {'type': 'list', 'items': [
                'TX to Pi RXD / GPIO15 (Pin 10)',
                'RX to Pi TXD / GPIO14 (Pin 8)',
                'GND to Pi GND'
            ]}
        ]
    )

    # 6. schematic_diagram_comprehsenive_explanation.docx
    create_doc(
        os.path.join(output_dir, 'schematic_diagram_comprehsenive_explanation.docx'),
        'Schematic Diagram & Comprehensive Explanation',
        [
            {'type': 'heading', 'text': '1. System Schematic Logic', 'level': 1},
            {'type': 'paragraph', 'text': 'The system follows a sequential pipeline: Data Acquisition -> Inference -> Analytics -> Presentation/Alerts.'},
            {'type': 'list', 'items': [
                'Camera & Thermal Input: Visual data is captured asynchronously while thermal grid data is captured via I2C.',
                'YOLOv8 & SORT: Visual data passes through ONNX YOLOv8n to generate bounding boxes. SORT assigns tracking IDs.',
                'Thermal Mapper: Matches bounding box centroids to regions in the 8x8 thermal grid.',
                'Risk Engine & Database: Assesses behaviors and temperatures. Logs state to SQLite.',
                'Outputs: Updates Flask Dashboard and triggers GSM SMS alerts if required.'
            ]}
        ]
    )

    # 7. datasets_and_training_model_comprehensive_explanation.docx
    create_doc(
        os.path.join(output_dir, 'datasets_and_training_model_comprehensive_explanation.docx'),
        'Datasets and Training Model Comprehensive Explanation',
        [
            {'type': 'heading', 'text': '1. Dataset Composition', 'level': 1},
            {'type': 'paragraph', 'text': 'The training data was created by merging multiple pig behavior datasets into a standardized 8-class format: lying, standing, walking, sitting, feeding, drinking, social_interaction, aggression. A total of 8,515 images were used in an 80/10/10 train/val/test split.'},
            {'type': 'heading', 'text': '2. YOLOv8n Model Architecture', 'level': 1},
            {'type': 'paragraph', 'text': 'YOLOv8 Nano was selected for its balance between accuracy and performance on CPU-bound edge devices like the Raspberry Pi. It was trained on an RTX 4050.'},
            {'type': 'heading', 'text': '3. Training Results & Metrics', 'level': 1},
            {'type': 'paragraph', 'text': 'The model achieved a high mAP50 (>0.82) on the evaluation set. Below are the visual results from the evaluation:'},
            {'type': 'image', 'path': r'runs\evaluate\test_evaluation\confusion_matrix_normalized.png', 'caption': 'Normalized Confusion Matrix'},
            {'type': 'image', 'path': r'runs\evaluate\test_evaluation\BoxF1_curve.png', 'caption': 'F1-Confidence Curve'},
            {'type': 'image', 'path': r'runs\evaluate\test_evaluation\BoxPR_curve.png', 'caption': 'Precision-Recall Curve'},
            {'type': 'image', 'path': r'runs\evaluate\test_evaluation\val_batch0_pred.jpg', 'caption': 'Validation Batch 0 Predictions'}
        ]
    )

if __name__ == '__main__':
    main()
