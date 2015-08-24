﻿from functools import partial
import threading
import abc
import time
try:
	import queue
except:
	import Queue
import sys


class ExThread(threading.Thread):
	def __init__(self, target=None,name=None):
		threading.Thread.__init__(self, target=target, name=name)
		self.__status_queue = queue.Queue()
		self.exc_raised = threading.Event()
		self.exc_raised.clear()
		self.target = target

	def run_with_exception(self):
		print("start thread")
		self.target()
	
	def run(self, delay=0):
		try:
			if delay > 0:
				import time
				time.sleep(delay)
			self.run_with_exception()
		except Exception:
			print("omg i got an exception", sys.exc_info())
			self.__status_queue.put(sys.exc_info())
		self.__status_queue.put(None)
	def runWithDelay(self, delay):
		#import time
		#time.sleep(delay)
		self.run(delay)
	
	def wait_for_exc_info(self):
	    return self.__status_queue.get(timeout=0.1)
	
	def join_with_exception(self):
		try:
			ex_info = self.wait_for_exc_info()
		except queue.Empty:
			return
		if ex_info is None:
			return
		else:
			raise ex_info[1]


class Callback:
	def __init__(self,parent):
		self.callback_chain = []
		self.currentIndex = 0
		self.parent = parent
		self.running = threading.Event()
		self.running.clear()
		self.addItem = threading.Event()
		self.addItem.clear()
		self.chain_lock = threading.RLock()
		
	
	def __call__(self):
		self.running.set()
		self.updateThread = ExThread(target = self.updateLoop, name="MainUpdateLoop")
		self.updateThread.start()
		return self.updateThread
	
	def stopUpdates(self):
		self.running.clear()
	
	def handleErrors(self, error):
		#handle errors occuring during callback_chain
		pass
	
	def updateLoop(self):
		print("in update loop", self.running.is_set())
		if not hasattr(self, "threads"):
			self.threads = {}
		self.currentIndex =0

		#with self.chain_lock:
		#	for functions in self.callback_chain:
				#get threads for each functions
		#		try:
		#			self.threads += [self.callObject(functions)]
		#		except:
		#			print("ooops")
		#			self.handleErrors("Error in calling")
		while self.running.is_set():
			#print("im here")
			flagRunning = False
			self.currentIndex = 0
			del_arr = []
			with self.chain_lock:
				for thread_name in self.threads:
					thread = self.threads[thread_name]
					print("check thread[%s]"%thread_name)
					try:
						thread.join_with_exception()
					except:
						#we had an exception, try to rerun the thread
						thread.run()
					if thread.is_alive():
						#check if the thread is dead
						flagRunning = True
						
					elif self.callback_chain[self.currentIndex][1]:
						try:
							thread.join_with_exception()
						except Exception:
							print("Thread could not recover")
						else:
						#if we have a continues thread restart it with the delay
							print("continues task, rerun it")
							thread.run(self.callback_chain[self.currentIndex][3])
							#thread.run()
							print("set delay to %d"%self.callback_chain[self.currentIndex][3])
							flagRunning = True
					else:
						try:
							thread.join_with_exception()
						except Exception:
							print("Fatal error, thread [" + thread_name + "] could not recover state...")
						else:
						#thread finished and is not continues so clear it from the list
							print("remove thread because it has finished", thread_name)
							currentCallback = self.callback_chain[self.currentIndex]
							del_arr += [currentCallback[2]]
							del self.callback_chain[self.currentIndex]
					if self.currentIndex + 1 < len(self.callback_chain):	
						self.currentIndex += 1
				for name in del_arr:
					#remove the entries from the dictionary
					del self.threads[name]
				if not flagRunning:
					#if callback_chain is empty stop updateLoop
					#we may want to continue the loop
					#self.running.clear()
					pass
				#print("propagateUpdate to master")
				#if we want to use that approach, we have to find a way to send an event to the mainthread
				#self.propagateUpdate()
			self.addItem.wait(10)
			self.addItem.clear()
	
	@abc.abstractmethod
	def propagateUpdate(self):
		"""Propagate the updaters to the parent"""
		return
	
	def callObject(self, func):
		try:
			localthread = ExThread(target=func[0])
			localthread.start()
			return localthread
		except Exception:
			print("could not start thread")
			return None
	
	def getEventPointer(self, func, name):
		return partial(func, self)
	
	def __setitem__(self, key, value):
		with self.chain_lock:
			#if we have a periodic task save the intervall
			functions = (value[0], value[1], key) if not value[1] else (value[0], value[1], key, value[2])
			self.callback_chain += [functions]
			if not hasattr(self, "threads"):
				self.threads = {}
			self.threads[key] = self.callObject(functions)
		self.addItem.set()
		
	def __contains__(self,key):
		return key in self.threads
class TkInterCallback(Callback):
	def propagateUpdate(self):
		#pass
		self.parent.update()
