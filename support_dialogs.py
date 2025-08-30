from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout

# For Multi Line Edit
class MultiLineTextDialog(QDialog):
    def __init__(self, parent=None, title="Edit Text", label_text="Text:", default_text=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 300)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(default_text)

        font = self.text_edit.font()
        font.setPointSize(17)
        self.text_edit.setFont(font)

        label = QLabel(label_text)

        button_ok = QPushButton("OK")
        button_cancel = QPushButton("Cancel")
        button_ok.clicked.connect(self.accept)
        button_cancel.clicked.connect(self.reject)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(button_ok)
        buttons_layout.addWidget(button_cancel)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.text_edit)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def getText(self):
        return self.text_edit.toPlainText()