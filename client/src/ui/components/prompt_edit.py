from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import pyqtSignal, Qt


class PromptEdit(QTextEdit):
    returnPressed = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.returnPressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)