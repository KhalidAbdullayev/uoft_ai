from __future__ import annotations

from PySide6.QtGui import QFontMetrics
from sentence_transformers import SentenceTransformer
import json
import faiss
from ollama import chat
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QSizePolicy
from typing import Any
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSize
import markdown

from PySide6.QtWidgets import *

NEW_CHAT = "New chat"

def get_chat(chats, chat_id):
    for cha in chats:
        if cha["id"] == chat_id:
            return cha
    return None

def new_message(sender: str, content: str):
    return {"role": sender, "content": content}


class ChatItem(QWidget):
    clicked = Signal(int)
    update_hist = Signal()

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
                with open("chats.json", encoding="utf8") as f:
                    chats = json.load(f)
                    cha = get_chat(chats, self.chat_id)
                    cha["title"] = text
                with open("chats.json", "w", encoding="utf8") as f:
                    # noinspection PyTypeChecker
                    json.dump(chats, f, ensure_ascii=False, indent=4)
                self.update_hist.emit()
        elif action == delete:
            reply = QMessageBox.question(self,"Delete chat","Delete this chat?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                with open("chats.json", encoding="utf8") as f:
                    chats = json.load(f)
                    cha = get_chat(chats, self.chat_id)
                    chats.remove(cha)
                with open("chats.json", "w", encoding="utf8") as f:
                    # noinspection PyTypeChecker
                    json.dump(chats, f, ensure_ascii=False, indent=4)
                self.update_hist.emit()
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

    def append(self, text):
        self.full_text += text
        html = markdown.markdown(self.full_text)
        self.label.setText(html)

# def ask_llm(ques: str, previous_chats: str, embedding_model: SentenceTransformer, index: Any,
#             chunks: Any):
#     question = embedding_model.encode(ques, normalize_embeddings=True, convert_to_numpy=True)
#
#     distances, indices = index.search(question.reshape(1, -1).astype("float32"), 5)
#
#     context = ""
#     for idx in indices[0]:
#         context += f"\nSource: {chunks[idx]['url']}\n" f"{chunks[idx]['text']}\n\n"
#
#     prompt = f"""
#     You are an assistant for new UTM students.
#
#     Use ONLY the provided context.
#
#     If the answer cannot be found in the context,
#     say that you don't know.
#
#     Always cite the page URL that you used.
#
#     Context:
#
#     {context}
#
#     Previous chats:
#     {previous_chats}
#
#     Question:
#
#     {ques}
#     """
#     # qwen2.5:3b
#     # qwen2.5:1.5b
#     # gemma3:1b
#     stream = chat(
#         model="qwen2.5:3b",
#         messages=[{"role": "user", "content": prompt}],
#         stream=True
#     )
#     previous_chats += f"""
#             Question:
#             {ques}
#             You replied:\n
#             """
#     answer = ""
#     for chunk in stream:
#         answer += chunk["message"]["content"]
#
#         # assistant_msg.append(chunk["message"]["content"])
#         # assistant_msg.updateGeometry()
#         # assistant_msg.repaint()
#         QApplication.processEvents()
#         previous_chats += chunk["message"]["content"]
#     # answer += "\n"
#     # chatting.append("")
#     previous_chats += "\n"
#     return answer, previous_chats

class TitleWorker(QThread):
    finished = Signal(str, int)

    def __init__(self, previous_chats, chat_id):
        super().__init__()

        self.previous_chats = previous_chats
        self.chat_id = chat_id

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


class ChatWorker(QThread):
    chunk_received = Signal(str)
    finished = Signal(str, str, int)   # answer, previous_chat, current_id

    def __init__(self, question, previous_chats, embedding_model, index, chunks, current_id):
        super().__init__()

        self.question = question
        self.previous_chats = previous_chats
        self.embedding_model = embedding_model
        self.index = index
        self.chunks = chunks
        self.current_id = current_id
        self.answer = ""

    def run(self):
        question_embedding = self.embedding_model.encode(
            self.question,
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        distances, indices = self.index.search(question_embedding.reshape(1, -1).astype("float32"), 5)
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

        stream = chat(
            model="qwen2.5:3b",
            messages=[new_message("user", prompt)],
            stream=True
        )
        self.answer = ""
        for chunk in stream:
            text = chunk["message"]["content"]
            self.answer += text
            self.chunk_received.emit(text)
        updated_history = self.previous_chats + f"""
        User:
        {self.question}

        Assistant
        {self.answer}
        """
        self.finished.emit(self.answer, updated_history, self.current_id)

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

        self.question = QLineEdit()
        self.button = QPushButton("Send")
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
        chat_layout.addWidget(self.question)
        chat_layout.addWidget(self.button)

        # Connecting
        main_layout.addWidget(sidebar, 1)
        main_layout.addWidget(chat_widget, 4)

        with open("chunks.json", encoding="utf8") as f:
            self.chunks = json.load(f)
        self.index = faiss.read_index("utm.index")

        self.embedding_model = SentenceTransformer("models/bge-small")


        self.prev_chats = ""
        # 2. Connect the button's clicked signal to your custom function
        self.button.clicked.connect(self.ask_model)
        self.question.returnPressed.connect(self.ask_model)
        self.workers = []
        self.current_id = current_id
        if current_id is not None:
            with open("chats.json", encoding="utf8") as f:
                chats = json.load(f)
                self.generate_chat(get_chat(chats, self.current_id))
                QApplication.processEvents()
        else:
            with open("chats.json", encoding="utf8") as f:
                chats = json.load(f)
                if chats is None:
                    self.current_id = 0
                else:
                    self.current_id = self.first_free_id(chats)
            #     chats.append({"id": self.current_id, "title": str(self.current_id), "messages": [],})
            # with open("chats.json", "w", encoding="utf8") as f:
            #     # noinspection PyTypeChecker
            #     json.dump(chats, f, ensure_ascii=False, indent=4)
        self.title_workers = []
        self.update_history(chats)

        self.history.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.history.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history.setStyleSheet("""
        QListWidget {
            border: none;
            outline: none;
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
            item.setSizeHint(widget.sizeHint())
            self.history.addItem(item)
            self.history.setItemWidget(item, widget)

    def update_history_chats(self):
        with open("chats.json", encoding="utf8") as f:
            chats = json.load(f)
            self.update_history(chats)

    def open_chat(self, chat_id):
        for i in range(self.history.count()):
            item = self.history.item(i)
            widget = self.history.itemWidget(item)
            if isinstance(widget, ChatItem):
                widget.selected = (widget.chat_id == chat_id)
                widget.update_style()

        self.current_id = chat_id
        # очистить окно сообщений
        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.prev_chats = ""
        with open("chats.json", encoding="utf8") as f:
            chats = json.load(f)
        cha = get_chat(chats, chat_id)
        self.generate_chat(cha)
        opened = True
        for worker in self.workers:
            if worker.current_id == self.current_id:
                assistant_msg = ChatMessage(worker.answer, False)
                self.chat_layout.addWidget(assistant_msg)
                worker.chunk_received.connect(assistant_msg.append)
                opened = False
        if opened:
            self.button.setEnabled(True)
        else:
            self.button.setEnabled(False)

    def new_chat(self):
        while self.chat_layout.count():
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        with open("chats.json", encoding="utf8") as f:
            chats = json.load(f)
        self.current_id = self.first_free_id(chats)
        # chats.append({
        #     "id": self.current_id,
        #     "title": str(self.current_id),
        #     "messages": []
        # })
        self.prev_chats = ""
        # with open("chats.json", "w", encoding="utf8") as f:
        #     # noinspection PyTypeChecker
        #     json.dump(chats, f, ensure_ascii=False, indent=4)
        self.update_history(chats)
        self.button.setEnabled(True)

    def chat_finished(self, answer, history, chat_id):
        for worker in self.workers:
            if worker.current_id == chat_id:
                self.workers.remove(worker)
                break
        if self.current_id == chat_id:
            self.prev_chats = history

        with open("chats.json", encoding="utf8") as f:
            chats = json.load(f)
            cha = get_chat(chats, chat_id)
            cha["messages"].append(new_message("assistant", answer))
            if cha["title"] == NEW_CHAT:
                title_worker = TitleWorker(history, chat_id)
                title_worker.finished.connect(self.title_finished)
                self.title_workers.append(title_worker)
                title_worker.start()

        with open("chats.json", "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)

        if chat_id == self.current_id:
            self.button.setEnabled(True)

    def title_finished(self, answer, chat_id):
        with open("chats.json", encoding="utf8") as f:
            chats = json.load(f)
            get_chat(chats, chat_id)["title"] = answer
        with open("chats.json", "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)
        self.update_history(chats)
        for title_worker in self.title_workers:
            if title_worker.chat_id == chat_id:
                self.title_workers.remove(title_worker)
                break

    # 3. Define the custom code you want to run
    def ask_model(self):
        question = self.question.text()

        with open("chats.json", encoding="utf8") as f:
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

        with open("chats.json", "w", encoding="utf8") as f:
            # noinspection PyTypeChecker
            json.dump(chats, f, ensure_ascii=False, indent=4)

        user_msg = ChatMessage(question, True)
        self.chat_layout.addWidget(user_msg)

        self.question.clear()
        assistant_msg = ChatMessage("")
        self.chat_layout.addWidget(assistant_msg)

        assistant_msg.updateGeometry()
        assistant_msg.repaint()
        QApplication.processEvents()

        worker = ChatWorker(question, self.prev_chats, self.embedding_model,
                                  self.index, self.chunks, self.current_id)
        self.workers.append(worker)
        worker.chunk_received.connect(assistant_msg.append)

        worker.finished.connect(self.chat_finished)
        self.button.setEnabled(False)
        worker.start()


app = QApplication([])

window = MainWindow()

window.show()

app.exec()