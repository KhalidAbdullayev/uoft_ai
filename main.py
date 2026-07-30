from __future__ import annotations

from PySide6.QtGui import QFontMetrics, QPixmap, QIcon
from sentence_transformers import SentenceTransformer
import json
import faiss
from ollama import chat
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QProgressBar
from PySide6.QtWidgets import QSizePolicy
from typing import Any
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize,QPropertyAnimation, QEasingCurve,\
                                                        QSequentialAnimationGroup, QPauseAnimation, QTimer, QObject,\
                                                        QUrl, QByteArray
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
import markdown
import os
import sys
import requests
import json


from PySide6.QtWidgets import *

NEW_CHAT = "New chat"

def get_chat(chats, chat_id):
    for cha in chats:
        if cha["id"] == chat_id:
            return cha
    return None

def new_message(sender: str, content: str):
    return {"role": sender, "content": content}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(__file__)

CHAT_FILE = os.path.join(BASE_DIR, "chats.json")

if not os.path.exists(CHAT_FILE):
    with open(CHAT_FILE, "w", encoding="utf8") as f:
        # noinspection PyTypeChecker
        json.dump([], f)

class Dot(QLabel):
    def __init__(self):
        super().__init__("●")

        self.setStyleSheet("""
            QLabel {
                color: gray;
                font-size: 18px;
            }
        """)

        self.anim = QSequentialAnimationGroup()

        up = QPropertyAnimation(self, b"pos")
        up.setDuration(180)
        up.setEasingCurve(QEasingCurve.Type.OutQuad)

        down = QPropertyAnimation(self, b"pos")
        down.setDuration(180)
        down.setEasingCurve(QEasingCurve.Type.InQuad)

        pause = QPauseAnimation(600)

        self.anim.addAnimation(up)
        self.anim.addAnimation(down)
        self.anim.addAnimation(pause)
        self.anim.finished.connect(self.anim.start)

        self.up = up
        self.down = down

class ThinkingWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        self.dots = []

        for _ in range(3):
            dot = Dot()
            layout.addWidget(dot)
            self.dots.append(dot)

        layout.addStretch()

        QTimer.singleShot(100, self.start_animation)

    def start_animation(self):

        for i, dot in enumerate(self.dots):

            start = dot.pos()

            dot.up.setStartValue(start)
            dot.up.setEndValue(start - QPoint(0, 8))

            dot.down.setStartValue(start - QPoint(0, 8))
            dot.down.setEndValue(start)

            QTimer.singleShot(i * 150, dot.anim.start)

class EmptyChat(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        layout.addStretch()

        self.logo = QLabel()

        pix = QPixmap(resource_path("uoft.png"))

        self.logo.setPixmap(pix.scaled(660, 660, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("UTM AI Assistant")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size:42px;
            font-weight:bold;
        """)

        subtitle = QLabel("Ask anything about the University of Toronto Mississauga")

        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle.setStyleSheet("""
            color:gray;
            font-size:21px;
        """)

        layout.addWidget(self.logo)
        layout.addSpacing(15)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(subtitle)

        layout.addStretch()

class SplashScreen(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Loading")

        layout = QVBoxLayout(self)

        title = QLabel("UTM AI Assistant")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel("Starting...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0,100)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        layout.addStretch()

        self.resize(400,180)

    def update_progress(self, value, text):
        self.progress.setValue(value)
        self.label.setText(text)
        QApplication.processEvents()

class ChatItem(QWidget):
    clicked = Signal(int)
    update_hist = Signal()
    delete_chat = Signal(int)

    def __init__(self, title, chat_id):
        super().__init__()


        self.chat_id = chat_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(title)
        self.label.setWordWrap(False)
        self.label.setContentsMargins(6, 4, 0, 0)

        self.menu_button = QPushButton("\u22EE")
        font = self.menu_button.font()
        font.setPointSize(14)
        self.menu_button.setFont(font)
        self.menu_button.hide()
        self.menu_button.setFixedSize(24, 24)

        self.menu_button.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 12px;
            padding: 0px;
            padding-bottom: 4px;
        }
        """)

        self.label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

        metrics = QFontMetrics(self.label.font())
        self.label.setText(
            metrics.elidedText(
                title,
                Qt.TextElideMode.ElideRight,
                200
            )
        )

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.menu_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.setContentsMargins(0, 2, 0, 5)
        layout.setSpacing(2)
        self.menu_button.clicked.connect(self.handle_menu)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.selected = False
        self.menu_open = False

        self.setStyleSheet("""
        ChatItem {
            border-radius: 8px;
            padding-left: 6px;
        }

        ChatItem:hover {
            background-color: #D8E9FF;
        }

        ChatItem[selected="true"] {
            background-color: #8DB9FF;
        }

        ChatItem[selected="true"]:hover {
            background-color: #8DB9FF;
        }
        """)

    def update_style(self):
        self.setProperty("selected", self.selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def enterEvent(self, event):
        self.menu_button.show()
        if not self.selected:
            self.setProperty("hover", True)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def leaveEvent(self, event):
        if not self.menu_open:
            self.menu_button.hide()

            if not self.selected:
                self.setProperty("hover", False)
                self.style().unpolish(self)
                self.style().polish(self)
                self.update()

    def mousePressEvent(self, event):
        self.clicked.emit(self.chat_id)
        event.accept()

    def handle_menu(self):
        self.menu_open = True
        menu = QMenu()

        rename = menu.addAction("Rename")
        delete = menu.addAction("Delete")

        action = menu.exec(self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height())))

        if action == rename:
            text, ok = QInputDialog.getText(self,"Rename chat", "New name:")
            if ok and text:
                with open(CHAT_FILE, encoding="utf8") as f:
                    chats = json.load(f)
                    cha = get_chat(chats, self.chat_id)
                    cha["title"] = text
                with open(CHAT_FILE, "w", encoding="utf8") as f:
                    # noinspection PyTypeChecker
                    json.dump(chats, f, ensure_ascii=False, indent=4)
                self.update_hist.emit()
        elif action == delete:
            reply = QMessageBox.question(self,"Delete chat","Delete this chat?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.delete_chat.emit(self.chat_id)
        self.menu_open = False
        self.menu_button.hide()
        self.update_style()


class ChatMessage(QFrame):
    def __init__(self, text="", is_user=False):
        super().__init__()

        self.label = QLabel(text)

        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )

        self.label.setOpenExternalLinks(True)

        self.label.setWordWrap(True)

        self.label.setText(markdown.markdown(text))

        self.label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )


        if is_user:
            self.setStyleSheet("""
                        QFrame {
                            background-color: #a9c3f5;
                            border-radius: 12px;
                            padding: 8px;
                        }
                    """)
        else:
            self.setStyleSheet("""
                        QFrame {
                            background-color: #FFFFFF;
                            border-radius: 12px;
                            padding: 8px;
                        }
                    """)
        self.full_text = text

    def append(self, text, current_id):
        self.full_text += text
        html = markdown.markdown(self.full_text)
        self.label.setText(html)

class ChatInput(QTextEdit):
    sendPressed = Signal()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.sendPressed.emit()
        else:
            super().keyPressEvent(event)

class TitleWorker(QThread):
    finished = Signal(str, int)

    def __init__(self, previous_chats, chat_id):
        super().__init__()
        self.previous_chats = previous_chats
        self.chat_id = chat_id
        self.reply = None
        self.network = QNetworkAccessManager(self)
        self.buffer = b""

    def run(self):
        prompt = f"""
            Generate a chat title.

            Rules:
            - Maximum 5 words.
            - No punctuation.
            - No quotation marks.
            - Output ONLY the title.
            - Do not explain your answer.
            Conversation:
            {self.previous_chats}
            """

        stream = chat(
            model="qwen2.5:1.5b",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            options={
                "num_predict": 10,
                "temperature": 0.2,
                "stop": ["\n"]
            }
        )
        answer = ""
        for chunk in stream:
            text = chunk["message"]["content"]
            answer += text
        answer = " ".join(answer.strip().replace('"', "").split()[:6])
        self.finished.emit(answer, self.chat_id)

class ChatWorker(QObject):

    chunk_received = Signal(str, int)
    finished = Signal(str, str, int) # answer, previous_chat, current_id

    def __init__(self, question, previous_chats, embedding_model, index, chunks, current_id):
        super().__init__()
        self.question = question
        self.previous_chats = previous_chats
        self.embedding_model = embedding_model
        self.index = index
        self.chunks = chunks
        self.current_id = current_id
        self.answer = ""
        self.reply = None
        self.network = QNetworkAccessManager(self)
        self.buffer = b""

    def stop(self):
        if self.reply:
            self.reply.abort()

    def start(self):
        question_embedding = self.embedding_model.encode(
            self.question,
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        distances, indices = self.index.search(
            question_embedding.reshape(1, -1).astype("float32"), 5
        )

        context = ""
        for idx in indices[0]:
            context += (
                f"\nSource: {self.chunks[idx]['url']}\n"
                f"{self.chunks[idx]['text']}\n\n"
            )

        prompt = f"""
    You are an assistant for new UTM students.

    Use ONLY the provided context.

    If the answer cannot be found in the context,
    say that you don't know.

    Always cite the page URL that you used.

    Context:

    {context}

    Previous chats:

    {self.previous_chats}

    Question:

    {self.question}
    """

        payload = {
            "model": "qwen2.5:3b",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": True
        }

        request = QNetworkRequest(
            QUrl("http://127.0.0.1:11434/api/chat")
        )

        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json"
        )

        self.reply = self.network.post(
            request,
            QByteArray(json.dumps(payload).encode())
        )

        self.reply.readyRead.connect(self.ready_read)
        self.reply.finished.connect(self.request_finished)

    def ready_read(self):
        if self.reply is None:
            return
        try:
            self.buffer += self.reply.readAll().data()
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                data = json.loads(line)
                text = data["message"]["content"]
                self.answer += text
                self.chunk_received.emit(text, self.current_id)
        except RuntimeError:
            return

    def request_finished(self):
        history = self.previous_chats + f"""
        User:
        {self.question}

        Assistant
        {self.answer}
        """

        self.finished.emit(self.answer, history, self.current_id)
        if self.reply is not None:
            try:
                self.reply.deleteLater()
            except RuntimeError:
                pass
            self.reply = None

class MainWindow(QMainWindow):
    def __init__(self, current_id = None):
        super().__init__()

        # 1. Create a button
        self.chat_layout = QVBoxLayout()
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        container = QWidget()
        # container.setSizePolicy(
        #     QSizePolicy.Policy.Preferred,
        #     QSizePolicy.Policy.Maximum
        # )
        container.setLayout(self.chat_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidget(container)
        self.scroll.setWidgetResizable(True)

        self.question = ChatInput()
        self.question.setFixedHeight(45)
        self.question.textChanged.connect(self.resize_input)
        self.question.sendPressed.connect(self.ask_model)
        self.question.setStyleSheet("""
        QTextEdit{
            border:1px solid #D0D0D0;
            border-radius:18px;
            padding:6px;
            font-size:16px;
            background:white;
        }

        QTextEdit:focus{
            border:1px solid #4A90E2;
        }
        """)

        font = self.question.font()
        font.setPointSize(14)
        self.question.setFont(font)
        self.question.setPlaceholderText("Ask anything about UTM...")

        self.send_button = QPushButton()
        self.send_button.setIcon(QIcon(str(resource_path("send.png"))))
        self.send_button.setIconSize(QSize(42, 42))
        # self.button.setFixedSize(42, 42)
        self.send_button.setStyleSheet("""
        QPushButton{
            border-radius:21px;
            background:transparent;
        }
        QPushButton:hover{
            background:transparent;
        }
        QPushButton:pressed{
            background:transparent;
        }
        """)

        self.setWindowTitle("UTM AI Assistant")

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        #left side
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        new_chat_button = QPushButton("New chat")

        self.history = QListWidget()

        sidebar_layout.addWidget(new_chat_button)
        sidebar_layout.addWidget(self.history)
        # Right side
        chat_widget = QWidget()

        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.addWidget(self.scroll)
        bottom = QHBoxLayout()
        bottom.addWidget(self.question)
        bottom.addWidget(self.send_button)
        chat_layout.addLayout(bottom)
        # chat_layout.addWidget(self.question)
        # chat_layout.addWidget(self.button)

        # Connecting
        main_layout.addWidget(sidebar, 1)
        main_layout.addWidget(chat_widget, 4)

        with open(resource_path("chunks.json"), encoding="utf8") as f:
            self.chunks = json.load(f)
            splash.update_progress(35, "Loading index...")
        self.index = faiss.read_index(str(resource_path("utm.index")))
        splash.update_progress(60, "Loading embedding model...")

        self.embedding_model = SentenceTransformer(str(resource_path("models/bge-small")))
        splash.update_progress(100, "Done")


        self.prev_chats = ""
        # 2. Connect the button's clicked signal to your custom function
        self.send_button.clicked.connect(self.send_button_clicked)
        # self.question.returnPressed.connect(self.ask_model)
        self.workers = []
        self.current_id = current_id
        if current_id is not None:
            with open(CHAT_FILE, encoding="utf8") as f:
                chats = json.load(f)
                self.generate_chat(get_chat(chats, self.current_id))
                QApplication.processEvents()
        else:
            with open(CHAT_FILE, encoding="utf8") as f:
                chats = json.load(f)
                if chats is None:
                    self.current_id = 0
                else:
                    self.current_id = self.first_free_id(chats)

        self.title_workers = []
        self.update_history(chats)

        self.history.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.history.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history.setStyleSheet("""
        QListWidget {
            background: white;
            border: none;
            border-radius: 8px;
            padding: 6px;
            background: white;
        }

        QListWidget::item {
            border: none;
            margin: 0px;
            padding: 0px;
        }

        QListWidget::item:selected {
            background: transparent;
        }

        QListWidget::item:hover {
            background: transparent;
        }
        """)

        new_chat_button.clicked.connect(self.new_chat)
        self.empty_chat = EmptyChat()
        self.chat_layout.addWidget(self.empty_chat, 1)
        self.thinking = None

    def generate_chat(self, cha):
        self.prev_chats = ""
        for message in cha["messages"]:
            msg = ChatMessage(message["content"], message["role"] == "user")
            self.chat_layout.addWidget(msg)
            if message["role"] == "user":
                self.prev_chats += f"User:\n{message['content']}\n\n"
            else:
                self.prev_chats += f"Assistant:\n{message['content']}\n\n"

    @staticmethod
    def first_free_id(chats):
        nums = []
        for cha in chats:
            nums.append(cha["id"])
        i = 0
        while True:
            if i not in nums:
                return i
            i += 1

    def update_history(self, chats):
        self.history.clear()
        for cha in chats:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 32))
            widget = ChatItem(cha["title"], cha["id"])

            if cha["id"] == self.current_id:
                widget.selected = True
                widget.update_style()

            widget.clicked.connect(self.open_chat)
            widget.update_hist.connect(self.update_history_chats)
            widget.delete_chat.connect(self.chat_deleted)
            item.setSizeHint(widget.sizeHint())
            self.history.addItem(item)
            self.history.setItemWidget(item, widget)

    def update_history_chats(self):
        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
            self.update_history(chats)

    def chat_deleted(self, chat_id):
        for worker in self.workers[:]:
            if worker.current_id == chat_id:
                worker.stop()
                break
        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
        cha = get_chat(chats, chat_id)
        if cha is not None:
            chats.remove(cha)
        with open(CHAT_FILE, "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)
        self.update_history(chats)
        if self.current_id == chat_id:
            self.new_chat()

    def open_chat(self, chat_id):
        if self.empty_chat is not None:
            self.chat_layout.removeWidget(self.empty_chat)
            self.empty_chat.deleteLater()
            self.empty_chat = None
        for i in range(self.history.count()):
            item = self.history.item(i)
            widget = self.history.itemWidget(item)
            if isinstance(widget, ChatItem):
                widget.selected = (widget.chat_id == chat_id)
                widget.update_style()
        if self.thinking is not None:
            self.chat_layout.removeWidget(self.thinking)
            self.thinking.deleteLater()
            self.thinking = None

        self.current_id = chat_id

        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.prev_chats = ""
        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
        cha = get_chat(chats, chat_id)
        self.generate_chat(cha)
        for worker in self.workers:
            if worker.current_id == self.current_id and worker.answer != "":
                assistant_msg = ChatMessage(worker.answer, False)
                self.chat_layout.addWidget(assistant_msg)
                worker.chunk_received.connect(assistant_msg.append)
            if worker.current_id == self.current_id and worker.answer == "":
                self.thinking = ThinkingWidget()
                self.chat_layout.addWidget(self.thinking)
                worker.chunk_received.connect(self.received_first)
                self.thinking.updateGeometry()
                self.thinking.repaint()
        self.update_send_button()

    def received_first(self, text, chat_id):
        if self.current_id == chat_id:
            if self.thinking is not None:
                self.chat_layout.removeWidget(self.thinking)
                self.thinking.deleteLater()
                self.thinking = None
        assistant_msg = ChatMessage(text)
        if self.current_id == chat_id:
            self.chat_layout.addWidget(assistant_msg)
        for worker in self.workers:
            if worker.current_id == chat_id:
                worker.chunk_received.disconnect(self.received_first)
                worker.chunk_received.connect(assistant_msg.append)

    def new_chat(self):
        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
        if self.thinking is not None:
            self.chat_layout.removeWidget(self.thinking)
            self.thinking.deleteLater()
            self.thinking = None
        self.current_id = self.first_free_id(chats)
        self.prev_chats = ""
        self.update_history(chats)
        self.empty_chat = EmptyChat()
        self.chat_layout.addWidget(self.empty_chat, 1)
        self.update_send_button()

    def chat_finished(self, answer, history, chat_id):
        for worker in self.workers:
            if worker.current_id == chat_id:
                self.workers.remove(worker)
                break
        received_any_answer = True
        if self.current_id == chat_id:
            self.prev_chats = history
            if self.thinking is not None:
                self.chat_layout.removeWidget(self.thinking)
                self.thinking.deleteLater()
                self.thinking = None
                received_any_answer = False
        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
            cha = get_chat(chats, chat_id)
            if cha is not None:
                if received_any_answer:
                    cha["messages"].append(new_message("assistant", answer))
                if cha["title"] == NEW_CHAT:
                    title_worker = TitleWorker(history, chat_id)
                    title_worker.finished.connect(self.title_finished)
                    self.title_workers.append(title_worker)
                    title_worker.start()

        with open(CHAT_FILE, "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)
        self.update_send_button()

    def title_finished(self, answer, chat_id):
        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
            if get_chat(chats, chat_id) is not None:
                get_chat(chats, chat_id)["title"] = answer
        with open(CHAT_FILE, "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)
        self.update_history(chats)
        for title_worker in self.title_workers:
            if title_worker.chat_id == chat_id:
                self.title_workers.remove(title_worker)
                break

    def is_working(self):
        for worker in self.workers:
            if worker.current_id == self.current_id:
                return True
        return False

    def update_send_button(self):
        if self.is_working():
            self.send_button.setIcon(QIcon(str(resource_path("stop.png"))))
        else:
            self.send_button.setIcon(QIcon(str(resource_path("send.png"))))

    def send_button_clicked(self):
        if self.is_working():
            self.stop_model()
        else:
            self.ask_model()

    def resize_input(self):
        document = self.question.document()

        h = int(document.size().height()) + 15

        h = max(45, h)
        h = min(180, h)

        self.question.setFixedHeight(h)

    # 3. Define the custom code you want to run
    def ask_model(self):
        if self.is_working():
            return
        if self.empty_chat is not None:
            self.chat_layout.removeWidget(self.empty_chat)
            self.empty_chat.deleteLater()
            self.empty_chat = None

        question = self.question.toPlainText().strip()

        with open(CHAT_FILE, encoding="utf8") as f:
            chats = json.load(f)
            if get_chat(chats, self.current_id) is None or len(chats) == 0:
                chats.insert(0, {
                    "id": self.current_id,
                    "title": NEW_CHAT,
                    "messages": []
                })
            else:
                cha = get_chat(chats, self.current_id)
                if chats[0] != cha:
                    chats.remove(cha)
                    chats.insert(0, cha)
            self.update_history(chats)
            get_chat(chats, self.current_id)["messages"].append(new_message("user", question))

        with open(CHAT_FILE, "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)

        user_msg = ChatMessage(question, True)
        self.chat_layout.addWidget(user_msg)

        self.question.clear()
        self.question.setFixedHeight(45)
        self.thinking = ThinkingWidget()
        self.chat_layout.addWidget(self.thinking)

        self.thinking.updateGeometry()
        self.thinking.repaint()
        QApplication.processEvents()

        worker = ChatWorker(question, self.prev_chats, self.embedding_model,
                                  self.index, self.chunks, self.current_id)
        self.workers.append(worker)
        worker.chunk_received.connect(self.received_first)

        worker.finished.connect(self.chat_finished)
        worker.start()
        self.update_send_button()

    def stop_model(self):
        for worker in self.workers:
            if worker.current_id == self.current_id:
                worker.stop()
                break
        self.update_send_button()


app = QApplication([])
app.setWindowIcon(QIcon(str(resource_path("icon.ico"))))

splash = SplashScreen()
splash.show()

splash.update_progress(10, "Loading chunks...")

QApplication.processEvents()

window = MainWindow()

splash.close()

window.show()

app.exec()
