"""Editor review of each DJ's persistent character notes."""
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QListWidget,QTextEdit,QPushButton
from character_library import CharacterLibrary,HOSTS

class CharacterDialog(QDialog):
    def __init__(self,data_dir,parent=None):
        super().__init__(parent);self.library=CharacterLibrary(data_dir)
        self.setWindowTitle('DJ character library');self.resize(800,600)
        box=QVBoxLayout(self)
        note=QLabel('Generated character details are candidates. Accept useful traits or backstory to carry them into future scripts. Reject contradictions or lines spoken by someone else. Only accepted notes for the selected DJ enter prompts; editor profiles and continuity take priority.')
        note.setWordWrap(True);box.addWidget(note)
        self.host=QComboBox();self.host.addItems(HOSTS);box.addWidget(self.host)
        self.items=QListWidget();box.addWidget(self.items,1)
        self.detail=QTextEdit();self.detail.setReadOnly(True);box.addWidget(self.detail)
        row=QHBoxLayout()
        for title,status in [('Accept','accepted'),('Reject','rejected'),('Return to candidates','candidate')]:
            button=QPushButton(title);button.clicked.connect(lambda checked=False,s=status:self.decide(s));row.addWidget(button)
        box.addLayout(row)
        self.manual=QTextEdit();self.manual.setPlaceholderText('Add an editor-established habit, preference or backstory fact.');self.manual.setMaximumHeight(75);box.addWidget(self.manual)
        add=QPushButton('Add editor note');add.clicked.connect(self.add_note);box.addWidget(add)
        self.status=QLabel('');self.status.setWordWrap(True);box.addWidget(self.status)
        close=QPushButton('Close');close.clicked.connect(self.accept);box.addWidget(close)
        self.host.currentTextChanged.connect(self.reload);self.items.currentRowChanged.connect(self.show_note);self.reload()
    def reload(self):
        try:self.rows=[r for r in self.library.load() if r['dj']==self.host.currentText()]
        except (OSError,ValueError) as exc:self.status.setText(str(exc));self.rows=[]
        self.items.clear();self.detail.clear()
        for row in self.rows:self.items.addItem('['+row['status']+'] '+row['text'])
        if self.rows:self.items.setCurrentRow(0)
    def show_note(self,index):
        if 0<=index<len(self.rows):
            r=self.rows[index];self.detail.setPlainText(r['text']+'\n\nSource: '+r['source']+'\nScript SHA-256: '+r.get('source_id',''))
    def decide(self,status):
        index=self.items.currentRow()
        if 0<=index<len(self.rows):
            try:self.library.decide(self.rows[index]['id'],status);self.reload()
            except (OSError,ValueError) as exc:self.status.setText(str(exc))
    def add_note(self):
        try:self.library.add(self.host.currentText(),self.manual.toPlainText());self.manual.clear();self.reload()
        except (OSError,ValueError) as exc:self.status.setText(str(exc))
