import os, time, math
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# LiverBiopsy
#

class LiverBiopsy(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "LiverBiopsy" # TODO make this more human readable by adding spaces
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
# LiverBiopsyWidget
#

class LiverBiopsyWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/LiverBiopsy.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    
    # Set up 
    self.setupCustomViews()
    
    self.calibrationErrorThresholdMm = 0.9
    
    self.logic = LiverBiopsyLogic()
    
    
    # Set up slicer scene
    self.setupScene()
    
    self.ui.fromCTFiducialWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.toReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)

    # connections
    self.ui.saveButton.connect('clicked(bool)', self.onSaveScene)
    self.ui.connectPLUSButton.connect('clicked(bool)', self.onConnectPLUS)
    self.ui.layoutComboBox.connect('activated(const QString &)', self.onChangeLayout)
    self.ui.needleSpinCalibrationButton.connect('clicked(bool)', self.needleSpinCalibration)
    self.ui.needlePivotCalibrationButton.connect('clicked(bool)', self.needlePivotCalibration)
    self.ui.stylusSpinCalibrationButton.connect('clicked(bool)', self.stylusSpinCalibration)
    self.ui.stylusPivotCalibrationButton.connect('clicked(bool)', self.stylusPivotCalibration)
    self.ui.initialCTRegistrationButton.connect('clicked(bool)', self.initialCTRegistration)
    self.ui.placeToReferenceFiducialButton.connect('clicked(bool)', self.placeToReferenceFiducial)
    
    self.toolCalibrationTimer = qt.QTimer()
    self.toolCalibrationTimer.setInterval(500)
    self.toolCalibrationTimer.setSingleShot(True)
    self.toolCalibrationTimer.connect('timeout()', self.toolCalibrationTimeout)
    
    self.ui.fromCTFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromCTFiducials', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromCTFiducialWidget.setNodeColor(qt.QColor(85,255,0,255))
    self.ui.toReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toReferenceFiducialWidget.setNodeColor(qt.QColor(255,170,0,255))
    
    self.ui.testButton.connect('clicked(bool)', self.onTestFunction)
    
    # Add vertical spacer
    self.layout.addStretch(1)
    
    # Setup Fiducial Registration Wizards
    self.setupFiducialRegistrationWizard()


  def setupScene(self):
    self.PIVOT_CALIBRATION = 0
    self.SPIN_CALIBRATION = 1
    
    self.modulePath = os.path.dirname(slicer.modules.liverbiopsy.path)
    self.moduleTransformsPath = os.path.join(self.modulePath, 'Resources/Transforms')
    
    self.toolCalibrationMode = self.PIVOT_CALIBRATION
    
    self.pivotCalibrationLogic = slicer.modules.pivotcalibration.logic()
    self.fiducialRegistrationLogic = slicer.modules.fiducialregistrationwizard.logic()
  
    # Models
    self.StylusModel_StylusTip = slicer.util.getFirstNodeByName('StylusModel','vtkMRMLModelNode')
    if not self.StylusModel_StylusTip:
      slicer.modules.createmodels.logic().CreateNeedle(60,1.0, 1.5, 0)
      self.StylusModel_StylusTip=slicer.util.getFirstNodeByName("NeedleModel",'vtkMRMLModelNode')
      self.StylusModel_StylusTip.GetDisplayNode().SetColor(0.33, 1.0, 1.0)
      self.StylusModel_StylusTip.SetName("StylusModel")
      self.StylusModel_StylusTip.GetDisplayNode().SliceIntersectionVisibilityOn()
    self.StylusModel_StylusTip.GetDisplayNode().SetColor(0,1,1)
    
    self.NeedleModel_NeedleTip = slicer.util.getFirstNodeByName('NeedleModel','vtkMRMLModelNode')
    if not self.NeedleModel_NeedleTip:
      slicer.modules.createmodels.logic().CreateNeedle(60,1.0, 1.5, 0)
      self.NeedleModel_NeedleTip=slicer.util.getFirstNodeByName("NeedleModel",'vtkMRMLModelNode')
      self.NeedleModel_NeedleTip.GetDisplayNode().SetColor(0.33, 1.0, 1.0)
      self.NeedleModel_NeedleTip.SetName("NeedleModel")
      self.NeedleModel_NeedleTip.GetDisplayNode().SliceIntersectionVisibilityOn()
    self.NeedleModel_NeedleTip.GetDisplayNode().SetColor(1,1,0)
      
    # Transforms
    
    # Setup Stylus Transforms
    self.StylusTipToStylus = slicer.util.getFirstNodeByName('StylusTipToStylus', className='vtkMRMLLinearTransformNode')
    if not self.StylusTipToStylus:
      self.StylusTipToStylusFilePath = os.path.join(self.moduleTransformsPath, 'StylusTipToStylus.h5')
      [success, self.StylusTipToStylus] = slicer.util.loadTransform(self.StylusTipToStylusFilePath, returnNode = True)
      if success == True:
        self.StylusTipToStylus.SetName("StylusTipToStylus")
        slicer.mrmlScene.AddNode(self.StylusTipToStylus)
      else:
        logging.debug('Could not load StylusTipToStylus from file')
        self.StylusTipToStylus = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'StylusTipToStylus')
        if not self.StylusTipToStylus:
          logging.debug('Failed: Creation of StylusTipToStylus transform')
        else:
          logging.debug('Creation of StylusTipToStylus transform')
          
    self.StylusBaseToStylus = slicer.util.getFirstNodeByName('StylusBaseToStylus', className='vtkMRMLLinearTransformNode')
    if not self.StylusBaseToStylus:
      StylusBaseToStylusFilePath = os.path.join(self.moduleTransformsPath, 'StylusBaseToStylus.h5')
      [success, self.StylusBaseToStylus] = slicer.util.loadTransform(StylusBaseToStylusFilePath, returnNode = True)
      if success == True:
        self.StylusBaseToStylus.SetName("StylusBaseToStylus")
        slicer.mrmlScene.AddNode(self.StylusBaseToStylus)
      else:
        logging.debug('Could not load StylusBaseToStylus from file')
        self.StylusBaseToStylus = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'StylusBaseToStylus')
        if not self.StylusBaseToStylus:
          logging.debug('Failed: Creation of StylusBaseToStylus transform')
        else:
          logging.debug('Creation of StylusBaseToStylus transform')
          
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
          
    self.NeedleBaseToNeedle = slicer.util.getFirstNodeByName('NeedleBaseToNeedle', className='vtkMRMLLinearTransformNode')
    if not self.NeedleBaseToNeedle:
      NeedleBaseToNeedleFilePath = os.path.join(self.moduleTransformsPath, 'NeedleBaseToNeedle.h5')
      [success, self.NeedleBaseToNeedle] = slicer.util.loadTransform(NeedleBaseToNeedleFilePath, returnNode = True)
      if success == True:
        self.NeedleBaseToNeedle.SetName("NeedleBaseToNeedle")
        slicer.mrmlScene.AddNode(self.NeedleBaseToNeedle)
      else:
        logging.debug('Could not load NeedleBaseToNeedle from file')
        self.NeedleBaseToNeedle = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'NeedleBaseToNeedle')
        if not self.NeedleBaseToNeedle:
          logging.debug('Failed: Creation of NeedleBaseToNeedle transform')
        else:
          logging.debug('Creation of NeedleBaseToNeedle transform')
          
    #Setup CT Transforms
    
    self.CTToReference = slicer.util.getFirstNodeByName('CTToReference', className='vtkMRMLLinearTransformNode')
    if not self.CTToReference:
      CTToReferenceFilePath = os.path.join(self.moduleTransformsPath, 'CTToReference.h5')
      [success, self.CTToReference] = slicer.util.loadTransform(CTToReferenceFilePath, returnNode = True)
      if success == True:
        self.CTToReference.SetName("CTToReference")
        slicer.mrmlScene.AddNode(self.CTToReference)
      else:
        logging.debug('Could not load CTToReference from file')
        self.CTToReference = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'CTToReference')
        if not self.CTToReference:
          logging.debug('Failed: Creation of CTToReference transform')
        else:
          logging.debug('Creation of CTToReference transform')

    # Set up ReferenceToRas
    # TODO confirm
    self.ReferenceToRas = slicer.util.getFirstNodeByName('ReferenceToRas', className='vtkMRMLLinearTransformNode')
    if not self.ReferenceToRas:
      self.ReferenceToRas=slicer.vtkMRMLLinearTransformNode()
      self.ReferenceToRas.SetName("ReferenceToRas")
      slicer.mrmlScene.AddNode(self.ReferenceToRas)
          
          
    # OpenIGTLink transforms
    
    self.StylusToReference = slicer.util.getFirstNodeByName('StylusToReference', className='vtkMRMLLinearTransformNode')
    if not self.StylusToReference:
      self.StylusToReference=slicer.vtkMRMLLinearTransformNode()
      self.StylusToReference.SetName("StylusToReference")
      slicer.mrmlScene.AddNode(self.StylusToReference)
      
    self.NeedleToReference = slicer.util.getFirstNodeByName('NeedleToReference', className='vtkMRMLLinearTransformNode')
    if not self.NeedleToReference:
      self.NeedleToReference=slicer.vtkMRMLLinearTransformNode()
      self.NeedleToReference.SetName("NeedleToReference")
      slicer.mrmlScene.AddNode(self.NeedleToReference)


    # Build Transform Tree
    self.StylusToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.StylusTipToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.StylusModel_StylusTip.SetAndObserveTransformNodeID(self.StylusTipToStylus.GetID())
    self.StylusBaseToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.NeedleToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.NeedleTipToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.NeedleModel_NeedleTip.SetAndObserveTransformNodeID(self.NeedleTipToNeedle.GetID())
    self.NeedleBaseToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    
    
    # Markups Nodes
    self.FromCTFiducialNode = slicer.util.getFirstNodeByName('FromCTFiducials', className='vtkMRMLMarkupsFiducialNode')
    if not self.FromCTFiducialNode:
      self.FromCTFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.FromCTFiducialNode.SetName('FromCTFiducials')
      slicer.mrmlScene.AddNode(self.FromCTFiducialNode)
      
    self.ToReferenceFiducialNode = slicer.util.getFirstNodeByName('ToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode')
    if not self.ToReferenceFiducialNode:
      self.ToReferenceFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.ToReferenceFiducialNode.SetName('ToReferenceFiducials')
      slicer.mrmlScene.AddNode(self.ToReferenceFiducialNode)


  def setupFiducialRegistrationWizard(self):
    # Fiducial Registration Wizard Set up
    
    # Patient Registration
    self.initialCTRegistrationFiducialRegistrationWizard = slicer.vtkMRMLFiducialRegistrationWizardNode().NewInstance()
    self.initialCTRegistrationFiducialRegistrationWizard.SetAndObserveFromFiducialListNodeId(self.ui.fromCTFiducialWidget.currentNode().GetID())
    self.initialCTRegistrationFiducialRegistrationWizard.SetAndObserveToFiducialListNodeId(self.ui.toReferenceFiducialWidget.currentNode().GetID())
    self.initialCTRegistrationFiducialRegistrationWizard.SetProbeTransformToNodeId(self.StylusTipToStylus.GetID())
    self.initialCTRegistrationFiducialRegistrationWizard.SetOutputTransformNodeId(self.CTToReference.GetID())
    


  def cleanup(self):
    pass


  def setupCustomViews(self):
    logging.debug('setupCustomViews')
  
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
    logging.debug('onSaveScene')
    
    if (self.ui.savePath.currentPath):
      savePath = self.ui.savePath.currentPath
      sceneSaveFilename = savePath + "/LiverBiopsy-saved-scene-" + time.strftime("%Y%m%d-%H%M%S") + ".mrb"

      # Save scene
      if slicer.util.saveScene(sceneSaveFilename):
        logging.info("Scene saved to: {0}".format(sceneSaveFilename))
      else:
        logging.error("Scene saving failed") 
      
      print("Scene saved")
    else:
      print("Invalid Input Value")


  def onChangeLayout(self):
    logging.debug('onChangeLayout')
    
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


  def stylusPivotCalibration(self):
    logging.debug('stylusPivotCalibration')
    
    self.toolCalibrationMode = self.PIVOT_CALIBRATION
    
    self.stylusCalibration()


  def stylusSpinCalibration(self):
    logging.debug('needleSpinCalibration')
    
    self.toolCalibrationMode = self.SPIN_CALIBRATION
    
    self.stylusCalibration()


  def stylusCalibration(self):
    logging.debug('stylusCalibration')
    
    self.toolCalibrationResultNode = self.StylusTipToStylus
    self.toolCalibrationResultName = 'StylusTipToStylus'
    self.toolToReferenceNode = self.StylusToReference
    self.toolToReferenceTransformName = 'StylusToReference'
    self.toolBeingCalibrated = 'Stylus'
    self.toolCalibrationToolBaseNode = self.StylusBaseToStylus
    self.toolCalibrationModel = self.StylusModel_StylusTip
    
    self.toolCalibrationStart()


  def needleSpinCalibration(self):
    logging.debug('needleSpinCalibration')
    
    self.toolCalibrationMode = self.SPIN_CALIBRATION
    
    self.needleCalibration()


  def needlePivotCalibration(self):
    logging.debug('needlePivotCalibration')
    
    self.toolCalibrationMode = self.PIVOT_CALIBRATION
    
    self.needleCalibration()


  def needleCalibration(self):
    logging.debug('needleCalibration')
    
    self.toolCalibrationResultNode = self.NeedleTipToNeedle
    self.toolCalibrationResultName = 'NeedleTipToNeedle'
    self.toolToReferenceNode = self.NeedleToReference
    self.toolToReferenceTransformName = 'NeedleToReference'
    self.toolBeingCalibrated = 'Needle'
    self.toolCalibrationToolBaseNode = self.NeedleBaseToNeedle
    self.toolCalibrationModel = self.NeedleModel_NeedleTip
    
    self.toolCalibrationStart()


  def toolCalibrationStart(self):
    logging.debug('toolCalibrationStart')
    
    self.pivotCalibrationLogic.SetAndObserveTransformNode(self.toolToReferenceNode)
    
    self.ui.needlePivotCalibrationButton.setEnabled(False)
    self.ui.needleSpinCalibrationButton.setEnabled(False)
    self.ui.stylusPivotCalibrationButton.setEnabled(False)
    self.ui.stylusSpinCalibrationButton.setEnabled(False)
    
    self.toolCalibrationStopTime = time.time()+float(5)
    self.pivotCalibrationLogic.SetRecordingState(True)
    self.toolCalibrationTimeout()


  def toolCalibrationTimeout(self):
    logging.debug('toolCalibrationTimeout')
    
    if self.toolBeingCalibrated == 'Needle':
      self.ui.needleCalibrationErrorLabel.setText("")
      self.ui.needleCalibrationCountdownLabel.setText("Calibrating for {0:.0f} more seconds".format(self.toolCalibrationStopTime - time.time()))
    elif self.toolBeingCalibrated == 'Stylus':
      self.ui.stylusCalibrationErrorLabel.setText("")
      self.ui.stylusCalibrationCountdownLabel.setText("Calibrating for {0:.0f} more seconds".format(self.toolCalibrationStopTime - time.time()))
    
    if(time.time()<self.toolCalibrationStopTime):
      # continue if calibration time isn't finished
      self.toolCalibrationTimer.start()
    else:
      # calibration completed
      self.toolCalibrationStop()


  def toolCalibrationStop(self):
    logging.debug('toolCalibrationStop')
    
    self.ui.needlePivotCalibrationButton.setEnabled(True)
    self.ui.needleSpinCalibrationButton.setEnabled(True)
    self.ui.stylusPivotCalibrationButton.setEnabled(True)
    self.ui.stylusSpinCalibrationButton.setEnabled(True)
      
    if self.toolCalibrationMode == self.PIVOT_CALIBRATION:
      calibrationSuccess = self.pivotCalibrationLogic.ComputePivotCalibration()
    else:
      calibrationSuccess = self.pivotCalibrationLogic.ComputeSpinCalibration()
      
    if not calibrationSuccess:
      if self.toolBeingCalibrated == 'Needle':
        self.ui.needleCalibrationCountdownLabel.setText("Calibration failed: ")
        self.ui.needleCalibrationErrorLabel.setText(self.pivotCalibrationLogic.GetErrorText())
      elif self.toolBeingCalibrated == 'Stylus':
        self.ui.stylusCalibrationCountdownLabel.setText("Calibration failed: ")
        self.ui.stylusCalibrationErrorLabel.setText(self.pivotCalibrationLogic.GetErrorText())
        
      self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
      return
      
    if self.toolCalibrationMode == self.PIVOT_CALIBRATION:
      if(self.pivotCalibrationLogic.GetPivotRMSE() >= float(self.calibrationErrorThresholdMm)):
        if self.toolBeingCalibrated == 'Needle':
          self.ui.needleCalibrationCountdownLabel.setText("Pivot Calibration failed:")
          self.ui.needleCalibrationErrorLabel.setText("Error = {0:.2f} mm").format(self.pivotCalibrationLogic.GetPivotRMSE())
        elif self.toolBeingCalibrated == 'Stylus':
          self.ui.stylusCalibrationCountdownLabel.setText("Pivot Calibration failed:")
          self.ui.stylusCalibrationErrorLabel.setText("Error = {0:.2f} mm").format(self.pivotCalibrationLogic.GetPivotRMSE())
          
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        return
    else:
      if(self.pivotCalibrationLogic.GetSpinRMSE() >= float(self.calibrationErrorThresholdMm)):
        if self.toolBeingCalibrated == 'Needle':
          self.ui.needleCalibrationCountdownLabel.setText("Spin calibration failed:")
          self.ui.needleCalibrationErrorLabel.setText("Error = {0:.2f} mm").format(self.pivotCalibrationLogic.GetSpinRMSE())
        elif self.toolBeingCalibrated == 'Stylus':
          self.ui.stylusCalibrationCountdownLabel.setText("Spin calibration failed:")
          self.ui.stylusCalibrationErrorLabel.setText("Error = {0:.2f} mm").format(self.pivotCalibrationLogic.GetSpinRMSE())
          
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        return
      
    toolTipToToolMatrix = vtk.vtkMatrix4x4()
    self.pivotCalibrationLogic.GetToolTipToToolMatrix(toolTipToToolMatrix)
    self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
    self.toolCalibrationResultNode.SetMatrixTransformToParent(toolTipToToolMatrix)
    slicer.util.saveNode(self.toolCalibrationResultNode, os.path.join(self.moduleTransformsPath, self.toolCalibrationResultName + ".h5"))
    
    if self.toolCalibrationMode == self.PIVOT_CALIBRATION:
      if self.toolBeingCalibrated == 'Needle':
        self.ui.needleCalibrationCountdownLabel.setText("Pivot calibration completed")
        self.ui.needleCalibrationErrorLabel.setText("Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetPivotRMSE()))
      elif self.toolBeingCalibrated == 'Stylus':
        self.ui.stylusCalibrationCountdownLabel.setText("Pivot calibration completed")
        self.ui.stylusCalibrationErrorLabel.setText("Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetPivotRMSE()))
        
      self.updateDisplayedToolLength()
      logging.debug("Pivot calibration completed. Tool: {0}. RMSE = {1:.2f} mm".format(self.toolCalibrationResultNode.GetName(), self.pivotCalibrationLogic.GetPivotRMSE()))
    else:
      if self.toolBeingCalibrated == 'Needle':
        self.ui.needleCalibrationCountdownLabel.setText("Spin calibration completed.")
        self.ui.needleCalibrationErrorLabel.setText("Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetSpinRMSE()))
      elif self.toolBeingCalibrated == 'Stylus':
        self.ui.stylusCalibrationCountdownLabel.setText("Spin calibration completed.")
        self.ui.stylusCalibrationErrorLabel.setText("Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetSpinRMSE()))
        
      logging.debug("Spin calibration completed. Tool: {0}. RMSE = {1:.2f} mm".format(self.toolCalibrationResultNode.GetName(), self.pivotCalibrationLogic.GetSpinRMSE()))


  def updateDisplayedToolLength(self):
    logging.debug("updateDisplayedToolLength")
    
    toolTipToToolBaseTransform = vtk.vtkMatrix4x4()
    self.toolCalibrationResultNode.GetMatrixTransformToNode(self.toolCalibrationToolBaseNode, toolTipToToolBaseTransform)
    toolLength = int(math.sqrt(toolTipToToolBaseTransform.GetElement(0,3)**2+toolTipToToolBaseTransform.GetElement(1,3)**2+toolTipToToolBaseTransform.GetElement(2,3)**2))
    # Update the needle model
    slicer.modules.createmodels.logic().CreateNeedle(toolLength,1.0, 1.5, False, self.toolCalibrationModel)


  def placeToReferenceFiducial(self):
    logging.debug("placeToReferenceFiducial")
    
    self.fiducialRegistrationLogic.GetMarkupsLogic().SetActiveListID(self.ui.toReferenceFiducialWidget.currentNode())
    self.fiducialRegistrationLogic.AddFiducial(self.initialCTRegistrationFiducialRegistrationWizard.GetProbeTransformToNode())


  def initialCTRegistration(self):
    logging.debug("initialCTRegistration")
    
    success = self.fiducialRegistrationLogic.UpdateCalibration(slicer.vtkMRMLFiducialRegistrationWizardNode().SafeDownCast(self.initialCTRegistrationFiducialRegistrationWizard))
    self.ui.initialCTRegistrationErrorLabel.setText(self.initialCTRegistrationFiducialRegistrationWizard.GetCalibrationStatusMessage())


  def saveTransforms(self):
    logging.debug("saveTransforms")
    
    slicer.util.saveNode(self.StylusTipToStylus, os.path.join(self.moduleTransformsPath, 'StylusTipToStylus' + ".h5"))
    slicer.util.saveNode(self.NeedleTipToNeedle, os.path.join(self.moduleTransformsPath, 'NeedleTipToNeedle' + ".h5"))
    slicer.util.saveNode(self.ReferenceToRas, os.path.join(self.moduleTransformsPath, 'ReferenceToRas' + ".h5"))
    slicer.util.saveNode(self.CTToReference, os.path.join(self.moduleTransformsPath, 'CTToReference' + ".h5"))


  def onTestFunction(self):
    if(self.initialCTRegistration):
      print("True")
  
  
    print(self.initialCTRegistrationFiducialRegistrationWizard)
    print(self.initialCTRegistrationFiducialRegistrationWizard.GetFromFiducialListNode())
    
    print(self.initialCTRegistrationFiducialRegistrationWizard.GetNodeReference("ToFiducialList"))
    
    print(slicer.mrmlScene.GetReferencedNodes(self.initialCTRegistrationFiducialRegistrationWizard))
    print(self.fiducialRegistrationLogic)
    
    print("End Test")


#
# LiverBiopsyLogic
#

class LiverBiopsyLogic(ScriptedLoadableModuleLogic):
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
 


class LiverBiopsyTest(ScriptedLoadableModuleTest):
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
    self.test_LiverBiopsy1()


  def test_LiverBiopsy1(self):
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
