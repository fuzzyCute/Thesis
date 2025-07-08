from PyQt6.QtCore import QObject, pyqtSignal

from FinalVars import ERROR_UNKNOWN_ERROR

class SubDivideWorker(QObject):
    finished = pyqtSignal(str, str, dict) #This will be the start, end, and llm_text from the other side
    error = pyqtSignal(int) # If there's an error It will return a number
    done = pyqtSignal()


    def __init__(self, start, end, get_llm_text_fn, parent=None):
        super().__init__(parent)
        self.start = start
        self.end = end
        self.get_llm_text = get_llm_text_fn

    def run(self):
        try:
            result = self.get_llm_text(self.start, self.end)
            if isinstance(result, int):
                self.error.emit(result)
            else:
                self.finished.emit(self.start, self.end, result)
        except Exception as e:
            self.error.emit(ERROR_UNKNOWN_ERROR)
        finally:
            self.done.emit()