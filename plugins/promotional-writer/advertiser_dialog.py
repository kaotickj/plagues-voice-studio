"""Guided advertiser interview with optional local-model follow-up questions."""
from copy import deepcopy
import re
import time
from PyQt6.QtCore import QObject,QThread,pyqtSignal,pyqtSlot
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
 QPlainTextEdit,QComboBox,QPushButton,QListWidget,QCheckBox)
from writer_core.runtime import WriterRuntime
from .advertisers import AdvertiserLibrary,FIELDS,missing_questions,interview_messages

class InterviewWorker(QObject):
 done=pyqtSignal(str);error=pyqtSignal(str);finished=pyqtSignal()
 def __init__(self,runtime,profile,brief):super().__init__();self.runtime=runtime;self.profile=profile;self.brief=brief
 @pyqtSlot()
 def run(self):
  try:self.done.emit(self.runtime.generate_messages(interview_messages(self.profile,self.brief),120)['text'])
  except Exception as exc:self.error.emit(str(exc))
  finally:self.finished.emit()

class AdvertiserDialog(QDialog):
 def __init__(self,context,settings,brief='',selected='',parent=None):
  super().__init__(parent);self.context=context;self.settings=settings;self.brief=brief
  self.library=AdvertiserLibrary(context.data_dir);self.profile={};self.session_answers=[]
  self.thread=self.worker=self.runtime=None
  self.setWindowTitle('Advertiser profiles and interview');self.resize(840,780)
  layout=QVBoxLayout(self)
  note=QLabel('Save reusable business facts here. Use the interview to fill gaps; the AI asks questions and you supply answers. Prices, deadlines and one-off offers can be kept campaign-only. Saved facts are supplied by you and should be checked when they change.')
  note.setWordWrap(True);layout.addWidget(note)
  self.choose=QComboBox();self.choose.setMinimumContentsLength(20);self.choose.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);layout.addWidget(self.choose)
  self.rows=self.library.load();self.choose.addItem('New advertiser…','')
  for r in self.rows:self.choose.addItem(r['name'],r['id'])
  form=QFormLayout();self.fields={}
  for key,label in FIELDS.items():
   field=QLineEdit();field.setMaxLength(4000);self.fields[key]=field;form.addRow(label,field)
  layout.addLayout(form)
  buttons=QHBoxLayout();self.ask=QPushButton('Ask AI follow-up questions');self.ask.clicked.connect(self.ask_model)
  self.stop=QPushButton('Stop');self.stop.setEnabled(False);self.stop.clicked.connect(self.cancel)
  buttons.addWidget(self.ask);buttons.addWidget(self.stop);layout.addLayout(buttons)
  self.questions=QListWidget();self.questions.setMaximumHeight(110);layout.addWidget(self.questions)
  self.answer=QPlainTextEdit();self.answer.setPlaceholderText('Answer the selected question, or enter “unknown” / “not decided”.');self.answer.setMaximumHeight(85);layout.addWidget(self.answer)
  self.reuse=QCheckBox('Reuse this answer in future campaigns');self.reuse.setChecked(True);layout.addWidget(self.reuse)
  self.questions.currentTextChanged.connect(lambda q:self.reuse.setChecked(not bool(re.search(r'price|discount|sale|date|deadline|schedule|availability|stock|limited|offer terms',q,re.I))))
  self.history=QComboBox();self.history.setMinimumContentsLength(20);self.history.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);layout.addWidget(self.history)
  history_row=QHBoxLayout()
  edit=QPushButton('Edit saved answer');edit.clicked.connect(self.edit_answer);history_row.addWidget(edit)
  remove=QPushButton('Remove saved answer');remove.clicked.connect(self.remove_answer);history_row.addWidget(remove)
  layout.addLayout(history_row)
  self.record=QPushButton('Save answer');self.record.clicked.connect(self.save_answer);layout.addWidget(self.record)
  self.status=QLabel('');self.status.setWordWrap(True);layout.addWidget(self.status)
  self.commit_button=QPushButton('Save profile and use');self.commit_button.clicked.connect(self.commit);layout.addWidget(self.commit_button)
  self.choose.currentIndexChanged.connect(self.select_profile)
  index=self.choose.findData(selected);self.choose.setCurrentIndex(max(0,index));self.select_profile()
 def select_profile(self):
  self.profile=deepcopy(next((r for r in self.rows if r['id']==self.choose.currentData()),{'answers':[]}))
  for key,field in self.fields.items():field.setText(self.profile.get(key,''))
  self.questions.clear();self.questions.addItems(missing_questions(self.profile));self.session_answers=[]
  if self.questions.count():self.questions.setCurrentRow(0)
  self.refresh_history()
  count=len(self.profile.get('answers',[]));self.status.setText(f'{count} saved answers. AI follow-up uses the selected local writing model.')
 def refresh_history(self):
  self.history.clear()
  for row in self.profile.get('answers',[]):self.history.addItem(('Reusable: ' if row.get('reuse') else 'Campaign only: ')+row['question'])
 def edit_answer(self):
  index=self.history.currentIndex()
  if index<0:return
  row=self.profile['answers'][index]
  self.questions.addItem(row['question']);self.questions.setCurrentRow(self.questions.count()-1)
  self.answer.setPlainText(row['answer']);self.reuse.setChecked(row.get('reuse',False))
 def remove_answer(self):
  index=self.history.currentIndex()
  if index<0:return
  self.profile=self.current();removed=self.profile['answers'].pop(index)
  self.session_answers=[r for r in self.session_answers if r['question']!=removed['question']]
  try:self.profile=self.library.save(self.profile);self.refresh_history()
  except (OSError,ValueError) as exc:self.status.setText(str(exc))
 def current(self):return dict(self.profile,**{k:f.text().strip() for k,f in self.fields.items()})
 @property
 def is_busy(self):return self.thread is not None
 def ask_model(self):
  if self.is_busy:return
  reason=self.context.can_generate()
  if reason:self.status.setText(reason);return
  try:
   self.runtime=WriterRuntime(self.settings,self.context.data_dir);self.runtime._paths()
  except (ValueError,OSError) as exc:self.status.setText('Configure Model setup first. '+str(exc));return
  interview_profile=self.current()
  interview_profile['answers']=[r for r in interview_profile.get('answers',[]) if r.get('reuse') or r in self.session_answers]
  self.thread=QThread(self);self.worker=InterviewWorker(self.runtime,interview_profile,self.brief);self.worker.moveToThread(self.thread)
  self.thread.started.connect(self.worker.run);self.worker.done.connect(self.show_questions);self.worker.error.connect(self.status.setText)
  self.worker.finished.connect(self.thread.quit);self.worker.finished.connect(self.worker.deleteLater)
  self.thread.finished.connect(self.thread.deleteLater);self.thread.finished.connect(self.finished)
  self.set_busy(True);self.status.setText('Thinking of useful missing details…');self.thread.start()
 def set_busy(self,busy):
  for widget in (self.choose,self.ask,self.record,self.commit_button,*self.fields.values()):widget.setEnabled(not busy)
  self.stop.setEnabled(busy)
 def show_questions(self,text):
  questions=[]
  for line in text.splitlines():
   line=re.sub(r'^\s*(?:[-*]|\d+[.)])\s*','',line).strip()
   if '?' in line and len(line)<=350:questions.append(line)
  self.questions.clear();self.questions.addItems(questions[:3])
  if self.questions.count():self.questions.setCurrentRow(0)
  self.status.setText('Answer a question, then ask again when you want more detail.' if questions else 'No usable questions returned. You can fill in the profile directly.')
 def finished(self):self.thread=self.worker=self.runtime=None;self.set_busy(False)
 def cancel(self):
  if self.runtime:self.runtime.cancel();self.status.setText('Stopping interview model…')
 def save_answer(self):
  item=self.questions.currentItem();answer=self.answer.toPlainText().strip()
  if not item or not answer:return
  if len(answer)>2000:self.status.setText('Keep this answer under 2,000 characters.');return
  self.profile=self.current()
  row=dict(question=item.text(),answer=answer,reuse=self.reuse.isChecked(),answered=time.time(),source='user answer')
  self.profile['answers']=[r for r in self.profile.get('answers',[]) if r['question']!=row['question']]+[row]
  try:self.profile=self.library.save(self.profile)
  except (ValueError,OSError) as exc:self.status.setText(str(exc));return
  self.session_answers=[r for r in self.session_answers if r['question']!=row['question']]
  if not row['reuse']:self.session_answers.append(row)
  self.refresh_history()
  self.questions.takeItem(self.questions.currentRow());self.answer.clear();self.status.setText('Answer saved. Only reusable answers carry into later campaigns.')
 def commit(self):
  try:self.profile=self.library.save(self.current())
  except (ValueError,OSError) as exc:self.status.setText(str(exc));return
  self.accept()
 def reject(self):
  if self.is_busy:self.cancel()
  else:super().reject()
 def closeEvent(self,event):
  if self.is_busy:self.cancel();event.ignore()
  else:super().closeEvent(event)
