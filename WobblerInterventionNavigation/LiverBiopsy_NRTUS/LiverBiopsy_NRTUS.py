import os, time
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# LiverBiopsy_NRTUS
#

class LiverBiopsy_NRTUS(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "LiverBiopsy_NRTUS" # TODO make this more human readable by adding spaces
    self.parent.categories = ["US guided intervention"]
    self.parent.dependencies = []
    self.parent.contributors = ["Abigael Schonewille (PerkLab)"] 
    self.parent.helpText = """
This is a module designed to be the framework for percutaneous interventions of the liver guided by 3D ultrasound. 
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
""" # replace with organization, grant and thanks.

#
# LiverBiopsy_NRTUSWidget
#

class LiverBiopsy_NRTUSWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/LiverBiopsy_NRTUS.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    
    # Set up 
    self.setupCustomViews()
    
    logic = LiverBiopsy_NRTUSLogic()
    logic.setupTransforms()

    # connections
    self.ui.saveButton.connect('clicked(bool)', self.onSaveScene)
    self.ui.connectPLUSButton.connect('clicked(bool)', self.onConnectPLUS)
    self.ui.layoutComboBox.connect('activated(const QString &)', self.onChangeLayout)
    self.ui.spinCalibrationButton.connect('clicked(bool)', self.onSpinCalibration)
    self.ui.pivotCalibrationButton.connect('clicked(bool)', self.onPivotCalibration)
    
    self.ui.testButton.connect('clicked(bool)', self.onTestFunction)

    # Add vertical spacer
    self.layout.addStretch(1)
    
    # Set up slicer scene
    self.setupScene()
    

    
    

  def setupScene(self):
		self.PIVOT_CALIBRATION = 0
		self.SPIN_CALIBRATION = 1
		
		self.modulePath = os.path.dirname(slicer.modules.liverbiopsy_nrtus.path)
    self.moduleTransformsPath = os.path.join(self.modulePath, 'Resources/Transforms')
		
		self.needleCalibrationMode = self.PIVOT_CALIBRATION
	
    # Models
   
    self.needleModel_NeedleTip = slicer.util.getFirstNodeByName('NeedleModel','vtkMRMLModelNode')
    if not self.needleModel_NeedleTip:
      slicer.modules.createmodels.logic().CreateNeedle(60,1.0, 1.5, 0)
      self.needleModel_NeedleTip=slicer.util.getFirstNodeByName("NeedleModel",'vtkMRMLModelNode')
      self.needleModel_NeedleTip.GetDisplayNode().SetColor(0.33, 1.0, 1.0)
      self.needleModel_NeedleTip.SetName("NeedleModel")
      self.needleModel_NeedleTip.GetDisplayNode().SliceIntersectionVisibilityOn()
      
    # Transforms
    
    # Setup Needle Transforms    
    self.NeedleTipToNeedle = slicer.util.getFirstNodeByName('NeedleTipToNeedle', className='vtkMRMLLinearTransformNode')
    if not self.NeedleTipToNeedle:
			needleTipToNeedleFilePath = os.path.join(self.moduleTransformsPath, 'NeedleTipToNeedle.h5')
			[success, self.NeedleTipToNeedle] = slicer.util.loadTransform(NeedleTipToNeedleFilePath, returnNode = True)
      if success == True:
				self.NeedleTipToNeedle.SetName("NeedleTipToNeedle")
        slicer.mrmlScene.AddNode(self.NeedleTipToNeedle)
      else:
				logging.debug('Could not load NeedleTipToNeedle from file')
        self.NeedleTipToNeedle = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'NeedleTipToNeedle')
        if not self.NeedleTipToNeedle:
          logging.debug('Failed: Creation of NeedleTipToNeedle transform')
        else:
          logging.debug('Creation of NeedleTipToNeedle transform')  
					
		# OpenIGTLink transforms
		self.NeedleToReference = slicer.util.getFirstNodeByName(
      'NeedleToReference', className='vtkMRMLLinearTransformNode')
    if not self.NeedleToReference:
      self.NeedleToReference=slicer.vtkMRMLLinearTransformNode()
      self.NeedleToReference.SetName("NeedleToReference")
      slicer.mrmlScene.AddNode(self.needleToReference)
     
  def cleanup(self):
    pass

  def setupCustomViews(self):
    RGBO3DLayout = (
      "<layout type=\"vertical\" split=\"true\" >"
      " <item splitSize=\"500\">"
      "  <layout type=\"horizontal\">"
      "   <item>"
      "    <view class=\"vtkMRMLSliceNode\" singletontag=\"Orange\">"
      "     <property name=\"orientation\" action=\"default\">Adaptive</property>"
      "     <property name=\"viewlabel\" action=\"default\">O</property>"
      "     <property name=\"viewcolor\" action=\"default\">#FFA500</property>"
      "    </view>"
      "   </item>"
      "   <item>"
      "    <view class=\"vtkMRMLViewNode\" singletontag=\"1\" verticalStretch=\"0\">"
      "     <property name=\"viewlabel\" action=\"default\">1</property>"
      "    </view>"
      "   </item>"
      "  </layout>"
      " </item>"
      " <item splitSize=\"500\">"
      "  <layout type=\"horizontal\">"
      "   <item>"
      "    <view class=\"vtkMRMLSliceNode\" singletontag=\"Red\">"
      "     <property name=\"orientation\" action=\"default\">Axial</property>"
      "     <property name=\"viewlabel\" action=\"default\">R</property>"
      "     <property name=\"viewcolor\" action=\"default\">#F34A33</property>"
      "    </view>"
      "   </item>"
      "   <item>"
      "    <view class=\"vtkMRMLSliceNode\" singletontag=\"Yellow\">"
      "     <property name=\"orientation\" action=\"default\">Sagittal</property>"
      "     <property name=\"viewlabel\" action=\"default\">Y</property>"
      "     <property name=\"viewcolor\" action=\"default\">#EDD54C</property>"
      "    </view>"
      "   </item>"
      "   <item>"
      "    <view class=\"vtkMRMLSliceNode\" singletontag=\"Green\">"
      "     <property name=\"orientation\" action=\"default\">Coronal</property>"
      "     <property name=\"viewlabel\" action=\"default\">G</property>"
      "     <property name=\"viewcolor\" action=\"default\">#6EB04B</property>"
      "    </view>"
      "   </item>"
      "  </layout>"
      " </item>"
      "</layout>")
      
    RGBO3DLayoutID=400

    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(RGBO3DLayoutID, RGBO3DLayout)
    
  def onConnectPLUS(self):
    pass
    
  def onSaveScene(self):
    if (self.ui.savePath.currentPath):
      savePath = self.ui.savePath.currentPath
      sceneSaveFilename = savePath + "/LiverBiopsy_NRTUS-saved-scene-" + time.strftime("%Y%m%d-%H%M%S") + ".mrb"

      # Save scene
      if slicer.util.saveScene(sceneSaveFilename):
        logging.info("Scene saved to: {0}".format(sceneSaveFilename))
      else:
        logging.error("Scene saving failed") 
      
      print("saved")
    else:
      print("Invalid Input Value")
      
  def onChangeLayout(self):
    view = self.ui.layoutComboBox.currentText
    print(view)
    
    if(view == "Conventional View"):
      requestedID =  2
    elif(view == "Red Slice View"):
      requestedID =  6
    elif(view == "RGBO3D View"):
      requestedID =  400
    else:
      print("Invalid Input Value")
    
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(requestedID)  
    
  def onSpinCalibration(self):
    logging.debug('onSpinCalibration')
    
    self.ui.pivotCalibrationButton.setEnabled(False)
    self.ui.spinCalibrationButton.setEnabled(False)
    
    logic = LiverBiopsy_NRTUSLogic()
    logic.spinCalibration()
    
    self.ui.pivotCalibrationButton.setEnabled(True)
    self.ui.spinCalibrationButton.setEnabled(True)

    
  def onPivotCalibration(self):
    logging.debug('onPivotCalibration')
    
    self.ui.pivotCalibrationButton.setEnabled(False)
    self.ui.spinCalibrationButton.setEnabled(False)
    
    
    
    self.calibrationTimeout(pivotCalibrationStopTime, "Pivot")
    
    self.ui.pivotCalibrationButton.setEnabled(True)
    self.ui.spinCalibrationButton.setEnabled(True)

'''
    logging.debug('pivotCalibration')
    
    

    self.NeedleToReference = slicer.util.getFirstNodeByName('NeedleToReference', className='vtkMRMLTransformNode')
    if not self.NeedleToReference:     
      logging.debug('Failed: Could not find NeedleToReference')
    
    self.pivotCalibrationLogic=slicer.modules.pivotcalibration.logic()
    
    self.pivotCalibrationResultTargetNode = self.NeedleTipToNeedle
    self.pivotCalibrationResultTargetName = 'NeedleTipToNeedle'
    
    self.pivotCalibrationLogic.SetAndObserveTransformNode( self.NeedleToReference )
    self.pivotCalibrationStopTime = time.time() + float(5)
    self.pivotCalibrationLogic.SetRecordingState(True)
    return self.pivotCalibrationStopTime
'''



  def calibrationTimeout(self, calibrationStopTime, mode):
    self.ui.countdownLabel.setText("Calibrating for {0:.0f} more seconds".format(calibrationStopTime-time.time()))
    
    if(time.time()<calibrationStopTime):
      # continue
      if mode == "Pivot":
        self.startPivotCalibration()
      else: # mode == "Spin"
        self.startSpinCalibration()
    else:
      # calibration completed
      if mode == "Pivot":
        self.stopPivotCalibration()
      else: # mode == "Spin"
        self.stopSpinCalibration()
  
  
  def onTestFunction(self):
    pass
        

#
# LiverBiopsy_NRTUSLogic
#

class LiverBiopsy_NRTUSLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  
  def setupTransforms(self):
    pass    
 


class LiverBiopsy_NRTUSTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_LiverBiopsy_NRTUS1()

  def test_LiverBiopsy_NRTUS1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    self.delayDisplay('Test passed!')
