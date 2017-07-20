#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4 import QtCore, QtGui

from vacumm.misc.cfgui import QtObject
from vacumm.misc.cfgui.models.sessions import Session
from vacumm.misc.cfgui.resources.ui.sessions import Ui_SessionsDialog
from vacumm.misc.cfgui.utils.ui import question_dialog


class SessionsDialog(QtObject, Ui_SessionsDialog, QtGui.QDialog):
	
	def __init__(self, controller, **kwargs):
		self.controller = controller
		QtObject.__init__(self, **kwargs)
		Ui_SessionsDialog.__init__(self)
		QtGui.QDialog.__init__(self)
		self.setupUi(self)
		
		self.combo_name.setAutoCompletion(False)
		self.combo_name.setCompleter(None)
		
		self.current_session_name = None
	
	def show(self):
		self.set_session(self.controller.get_current_session())
		QtGui.QDialog.show(self)
		self.raise_()
		self.activateWindow()
	
	def set_session(self, session):
		self.debug('set_session:\n%s', session.to_xml_str())
		self.current_session_name = session.name
		self.combo_name.setEditText(session.name)
		self.line_specification.setText(session.specification_file)
		self.line_configuration.setText(session.configuration_file)
		self.update_combo_name()
	
	def get_session(self):
		session = Session(
			name=unicode(self.combo_name.currentText()),
			specification_file=unicode(self.line_specification.text()),
			configuration_file=unicode(self.line_configuration.text())
		)
		self.debug('get_session:\n%s', session.to_xml_str())
		return session
	
	def update_combo_name(self):
		session = self.get_session()
		items = sorted(self.controller.sessions.keys())
		if session.name not in items:
			items.append(unicode(session.name))
		name = unicode(self.combo_name.currentText())
		self.debug('update_combo_name: %(items)r %(name)r', locals())
		
		self.combo_name.clear()
		self.combo_name.addItems(items)
		#self.combo_name.setEditText(session.name)
		if name in items:
			self.combo_name.setCurrentIndex(items.index(session.name))
	
	def on_button_new(self):
		self.set_session(Session(name='New session'))
	
	def on_button_save(self):
		session = self.get_session()
		self.controller.set_session(session, replace=self.current_session_name)
		self.controller.save_sessions()
		self.set_session(session)
	
	def on_button_open(self):
		self.hide()
		self.controller.load_session(self.get_session())
	
	def on_button_delete(self):
		name = unicode(self.combo_name.currentText())
		if name and question_dialog('Delete session "%s"'%name):
			self.controller.delete_session(name)
			self.controller.save_sessions()
			self.update_combo_name()
			self.set_session(Session())
	
	def on_button_close(self):
		#QtGui.QDialog.reject(self)
		self.hide()
	
	def on_combo_name(self):
		name = unicode(self.combo_name.currentText())
		self.set_session(self.controller.get_session(name))
	
	def on_button_specification(self):
		path = QtGui.QFileDialog.getOpenFileName(filter=Session.specification_file_filter)
		if not path:
			return
		self.line_specification.setText(path)
	
	def on_button_configuration(self):
		path = QtGui.QFileDialog.getOpenFileName(filter=Session.configuration_file_filter)
		if not path:
			return
		self.line_configuration.setText(path)

