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
    
    self.calibrationErrorThresholdMm = 0.9
    
    logic = LiverBiopsy_NRTUSLogic()
    logic.setupTransforms()

    # connections
    self.ui.saveButton.connect('clicked(bool)', self.onSaveScene)
    self.ui.connectPLUSButton.connect('clicked(bool)', self.onConnectPLUS)
    self.ui.layoutComboBox.connect('activated(const QString &)', self.onChangeLayout)
    self.ui.spinCalibrationButton.connect('clicked(bool)', self.onSpinCalibration)
    self.ui.pivotCalibrationButton.connect('clicked(bool)', self.onPivotCalibration)
    
    self.ui.needleCalibrationSamplingTimer = qt.QTimer()
    self.ui.needleCalibrationSamplingTimer.setInterval(500)
    self.ui.needleCalibrationSamplingTimer.setSingleShot(True)
    self.ui.needleCalibrationSamplingTimer.connect('timeout()', self.needleCalibrationTimeout)
    
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
    
    self.pivotCalibrationLogic = slicer.modules.pivotcalibration.logic()
  
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
      self.NeedleTipToNeedleFilePath = os.path.join(self.moduleTransformsPath, 'NeedleTipToNeedle.h5')
      [success, self.NeedleTipToNeedle] = slicer.util.loadTransform(self.NeedleTipToNeedleFilePath, returnNode = True)
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

    # Set up ReferenceToRas
    # TODO confirm with tracking
    self.ReferenceToRas = slicer.util.getFirstNodeByName('ReferenceToRas', className='vtkMRMLLinearTransformNode')
    if not self.ReferenceToRas:
      self.ReferenceToRas=slicer.vtkMRMLLinearTransformNode()
      self.ReferenceToRas.SetName("ReferenceToRas")
      slicer.mrmlScene.AddNode(self.ReferenceToRas)

    self.NeedleToReference = slicer.util.getFirstNodeByName('NeedleToReference', className='vtkMRMLLinearTransformNode')
    if not self.NeedleToReference:
      self.NeedleToReference=slicer.vtkMRMLLinearTransformNode()
      self.NeedleToReference.SetName("NeedleToReference")
      slicer.mrmlScene.AddNode(self.NeedleToReference)

    # Build Transform Tree
    self.NeedleToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.NeedleTipToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.needleModel_NeedleTip.SetAndObserveTransformNodeID(self.NeedleTipToNeedle.GetID())


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
      requestedID = 2
    elif(view == "Red Slice View"):
      requestedID = 6
    elif(view == "RGBO3D View"):
      requestedID = 400
    else:
      print("Invalid Input Value")
    
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(requestedID)  


  def onSpinCalibration(self):
    logging.debug('onSpinCalibration')
    
    self.needleCalibrationMode = self.SPIN_CALIBRATION
    self.needleCalibrationStart()


  def onPivotCalibration(self):
    logging.debug('onPivotCalibration')
    
    self.needleCalibrationMode = self.PIVOT_CALIBRATION
    self.needleCalibrationStart()


  def needleCalibrationStart(self):
    logging.debug('needleCalibrationStart')
    
    self.ui.pivotCalibrationButton.setEnabled(False)
    self.ui.spinCalibrationButton.setEnabled(False)
    
    self.needleCalibrationResultNode = self.NeedleTipToNeedle
    self.needleCalibrationResultName = 'NeedleTipToNeedle'
    
    self.pivotCalibrationLogic.SetAndObserveTransformNode(self.NeedleToReference)
    
    self.needleCalibrationStopTime = time.time()+float(5)
    self.pivotCalibrationLogic.SetRecordingState(True)
    self.needleCalibrationTimeout()


  def needleCalibrationTimeout(self):
    logging.debug('needleCalibrationTimeout')
    
    self.ui.calibrationErrorLabel.setText("")
    self.ui.countdownLabel.setText("Calibrating for {0:.0f} more seconds".format(self.needleCalibrationStopTime - time.time()))
    
    if(time.time()<self.needleCalibrationStopTime):
      # continue if calibration time isn't finished
      self.ui.needleCalibrationSamplingTimer.start()
    else:
      # calibration completed
      self.stopNeedleCalibration()


  def stopNeedleCalibration(self):
    logging.debug('stopNeedleCalibration')
    
    self.ui.pivotCalibrationButton.setEnabled(True)
    self.ui.spinCalibrationButton.setEnabled(True)
    
    if self.needleCalibrationMode == self.PIVOT_CALIBRATION:
      calibrationSuccess = self.pivotCalibrationLogic.ComputePivotCalibration()
    else:
      calibrationSuccess = self.pivotCalibrationLogic.ComputeSpinCalibration()
      
    if not calibrationSuccess:
      self.ui.countdownLabel.setText("Calibration failed: ")
      self.ui.calibrationErrorLabel.setText(self.pivotCalibrationLogic.GetErrorText())
      self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
      return
      
    if self.needleCalibrationMode == self.PIVOT_CALIBRATION:
      if(self.pivotCalibrationLogic.GetPivotRMSE() >= float(self.calibrationErrorThresholdMm)):
        self.ui.countdownLabel.setText("Pivot Calibration failed:")
        self.ui.calibrationErrorLabel.setText("Error = {0:.2f} mm").format(self.pivotCalibrationLogic.GetPivotRMSE())
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        return
    else:
      if(self.pivotCalibrationLogic.GetSpinRMSE() >= float(self.calibrationErrorThresholdMm)):
        self.ui.countdownLabel.setText("Spin calibration failed:")
        self.ui.calibrationErrorLabel.setText("Error = {0:.2f} mm").format(self.pivotCalibrationLogic.GetSpinRMSE())
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        return
      
    NeedleTipToNeedleMatrix = vtk.vtkMatrix4x4()
    self.pivotCalibrationLogic.GetToolTipToToolMatrix(NeedleTipToNeedleMatrix)
    self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
    self.needleCalibrationResultNode.SetMatrixTransformToParent(NeedleTipToNeedleMatrix)
    slicer.util.saveNode(self.needleCalibrationResultNode, os.path.join(self.moduleTransformsPath, self.needleCalibrationResultName + ".h5"))
    
    if self.needleCalibrationMode == self.PIVOT_CALIBRATION:
      self.ui.countdownLabel.setText("Pivot calibration completed")
      self.ui.calibrationErrorLabel.setText("Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetPivotRMSE()))
      logging.debug("Pivot calibration completed. Tool: {0}. RMSE = {1:.2f} mm".format(self.needleCalibrationResultNode.GetName(), self.pivotCalibrationLogic.GetPivotRMSE()))
    else:
      self.ui.countdownLabel.setText("Spin calibration completed.")
      self.ui.calibrationErrorLabel.setText("Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetSpinRMSE()))
      logging.debug("Spin calibration completed. Tool: {0}. RMSE = {1:.2f} mm".format(self.needleCalibrationResultNode.GetName(), self.pivotCalibrationLogic.GetSpinRMSE()))
     
    # Compute approximate needle length if we perform pivot calibration for the needle and update needle model
    if self.needleCalibrationResultName == 'NeedleTipToNeedle':
      self.updateDisplayedNeedleLength()


  def updateDisplayedNeedleLength(self):
    pass


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
