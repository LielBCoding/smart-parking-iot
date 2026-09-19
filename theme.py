"""dark stylesheet"""
from PyQt5.QtGui import QFont

STYLE = """
QWidget {
    background-color: #1e272e;
    color: #ecf0f1;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QGroupBox {
    background-color: #2f3640;
    border: 1px solid #3d4a57;
    border-radius: 10px;
    margin-top: 16px;
    padding: 14px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #dcdde1;
    font-weight: bold;
    font-size: 14px;
}
QLabel { background: transparent; }
QPushButton {
    background-color: #3d4a57;
    border: 1px solid #57606f;
    border-radius: 6px;
    padding: 6px 14px;
    color: #f5f6fa;
}
QPushButton:hover { background-color: #4b5966; }
QPushButton:pressed { background-color: #2f3640; }
QLineEdit, QSpinBox, QTextEdit {
    background-color: #111518;
    border: 1px solid #3d4a57;
    border-radius: 6px;
    color: #ecf0f1;
    padding: 3px;
}
QCheckBox { spacing: 8px; }
QProgressBar {
    background-color: #111518;
    border: 1px solid #3d4a57;
    border-radius: 6px;
    text-align: center;
    color: #ecf0f1;
    height: 22px;
}
QProgressBar::chunk { background-color: #27ae60; border-radius: 5px; }
QSlider::groove:horizontal { height: 6px; background: #3d4a57; border-radius: 3px; }
QSlider::handle:horizontal { background: #f5f6fa; width: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #2980b9; border-radius: 3px; }
QScrollBar:vertical { background: #2f3640; width: 10px; }
QScrollBar::handle:vertical { background: #57606f; border-radius: 5px; min-height: 20px; }
"""


def apply_theme(app):
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
