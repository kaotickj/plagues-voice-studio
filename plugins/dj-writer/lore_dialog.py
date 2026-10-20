"""Reference library viewer and background wiki topic lookup."""
from copy import deepcopy
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QListWidget,QTextEdit,QCheckBox)
from lore_library import LoreLibrary
from character_dialog import CharacterDialog
from ai_writer import save_settings

class LookupWorker(QObject):
    done=pyqtSignal(str)
    finished=pyqtSignal()
    def __init__(self,library,topic):
        super().__init__(); self.library=library; self.topic=topic
    @pyqtSlot()
    def run(self):
        try:
            item=self.library.lookup(self.topic,refresh=True)
            self.done.emit('Saved wiki reference: '+item['title'])
        except Exception as exc:
            self.done.emit('Lookup failed; saved references are unchanged. '+str(exc))
        finally:
            self.finished.emit()

class LoreDialog(QDialog):
    def __init__(self,settings,data_dir,parent=None):
        super().__init__(parent)
        self.settings=deepcopy(settings); self.data_dir=data_dir
        self.library=LoreLibrary(data_dir); self.thread=None; self.worker=None
        self.setWindowTitle('Commonwealth lore library'); self.resize(850,650)
        layout=QVBoxLayout(self)
        note=QLabel('Curated notes and saved Independent Fallout Wiki references. Wiki references are not approved continuity. '
                    'Only topic names are sent online; briefs, scripts and profiles stay local. Lookups may contain spoilers. '
                    'Saved articles are reused offline; automatic lookups refresh after 30 days.')
        note.setWordWrap(True);layout.addWidget(note)
        self.auto=QCheckBox('Automatically look up relevant topics before writing')
        self.auto.setChecked(settings.get('wiki_lookup',True)); layout.addWidget(self.auto)
        row=QHBoxLayout();self.topic=QLineEdit();self.topic.setPlaceholderText('Wiki topic, e.g. Diamond City or Nick Valentine')
        self.lookup=QPushButton('Look up / refresh');self.lookup.clicked.connect(self.start_lookup)
        row.addWidget(self.topic);row.addWidget(self.lookup);layout.addLayout(row)
        self.items=QListWidget();layout.addWidget(self.items,1)
        self.preview=QTextEdit();self.preview.setReadOnly(True);layout.addWidget(self.preview,2)
        self.items.currentRowChanged.connect(self.show_record)
        self.status=QLabel('');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.remove=QPushButton('Remove selected saved wiki reference');self.remove.clicked.connect(self.remove_selected);layout.addWidget(self.remove)
        self.close_button=QPushButton('Save and close');self.close_button.clicked.connect(self.commit);layout.addWidget(self.close_button)
        characters=QPushButton('DJ character notes');characters.clicked.connect(self.open_characters);layout.addWidget(characters)
        self.reload()
    def open_characters(self):
        CharacterDialog(self.data_dir,self).exec()
    def reload(self):
        self.records=self.library.records();self.items.clear()
        for r in self.records:self.items.addItem(r['title']+' ['+r['kind']+']')
        if self.records:self.items.setCurrentRow(0)
    def show_record(self,index):
        if 0<=index<len(self.records):
            r=self.records[index]
            self.preview.setPlainText(r['text']+'\n\nSource: '+r['url']+'\nRevision: '+str(r.get('revision') or 'curated note')+'\n'+r.get('attribution','Original factual summary; source link for verification.')+'\nLicense: '+r.get('license','Original project notes')+'\n'+r.get('rights_url','')+'\n'+r.get('scope',''))
    def remove_selected(self):
        import hashlib
        index=self.items.currentRow()
        if 0<=index<len(self.records) and self.records[index]['kind']=='wiki':
            name=hashlib.sha256(self.records[index]['title'].casefold().encode()).hexdigest()+'.json'
            try:self.library.remove(self.records[index]['title'])
            except OSError as exc:self.status.setText(str(exc));return
            self.reload()
    def start_lookup(self):
        topic=self.topic.text().strip()
        if not topic:return
        self.lookup.setEnabled(False);self.close_button.setEnabled(False);self.remove.setEnabled(False)
        self.status.setText('Looking up '+topic+'...')
        self.thread=QThread(self);self.worker=LookupWorker(self.library,topic);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.done.connect(self.finished_lookup)
        self.worker.finished.connect(self.thread.quit);self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater);self.thread.finished.connect(self.thread_done)
        self.thread.start()
    def finished_lookup(self,message):
        self.status.setText(message);self.reload()
    def thread_done(self):
        self.thread=None;self.worker=None;self.lookup.setEnabled(True);self.close_button.setEnabled(True);self.remove.setEnabled(True)
    def commit(self):
        self.settings['wiki_lookup']=self.auto.isChecked()
        try:save_settings(self.data_dir/'ai_studio.json',self.settings)
        except (ValueError,OSError) as exc:self.status.setText(str(exc));return
        self.accept()
    def reject(self):
        if self.thread is None:super().reject()
    def closeEvent(self,event):
        if self.thread is not None:event.ignore()
        else:super().closeEvent(event)
