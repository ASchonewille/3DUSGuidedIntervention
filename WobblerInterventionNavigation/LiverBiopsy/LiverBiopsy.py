import os, time, math
import ScreenCapture
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
    self.parent.title = "LiverBiopsy"
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

    self.ui.fromProbeToUSFiducialWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.toProbeToUSFiducialWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.fromCTToReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.toCTToReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)

    # connections
    
    self.ui.saveButton.connect('clicked(bool)', self.onSaveScene)
    self.ui.connectPLUSButton.connect('clicked(bool)', self.onConnectPLUS)
    self.ui.layoutComboBox.connect('activated(const QString &)', self.onChangeLayout)
    self.ui.needleSpinCalibrationButton.connect('clicked(bool)', self.needleSpinCalibration)
    self.ui.needlePivotCalibrationButton.connect('clicked(bool)', self.needlePivotCalibration)
    self.ui.stylusSpinCalibrationButton.connect('clicked(bool)', self.stylusSpinCalibration)
    self.ui.stylusPivotCalibrationButton.connect('clicked(bool)', self.stylusPivotCalibration)
    self.ui.USCalibrationButton.connect('clicked(bool)', self.USCalibration)
    self.ui.initialCTRegistrationButton.connect('clicked(bool)', self.initialCTRegistration)
    self.ui.placeToCTToReferenceFiducialButton.connect('clicked(bool)', self.placeToCTToReferenceFiducial)
    self.ui.freezeUltrasoundButton.connect('clicked(bool)', self.onFreezeUltrasound)

    self.toolCalibrationTimer = qt.QTimer()
    self.toolCalibrationTimer.setInterval(500)
    self.toolCalibrationTimer.connect('timeout()', self.toolCalibrationTimeout)

    self.ui.fromProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromProbeToUSFiducialWidget.setNodeColor(qt.QColor(207,26,0,255))
    self.ui.toProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toProbeToUSFiducialWidget.setNodeColor(qt.QColor(103,0,225,255))
    
    self.ui.fromCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromCTToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromCTToReferenceFiducialWidget.setNodeColor(qt.QColor(85,255,0,255))
    self.ui.toCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToCTToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toCTToReferenceFiducialWidget.setNodeColor(qt.QColor(255,170,0,255))
    
    self.ui.testButton.connect('clicked(bool)', self.onTestFunction)


  def setupScene(self):
    self.PIVOT_CALIBRATION = 0
    self.SPIN_CALIBRATION = 1
    
    self.modulePath = os.path.dirname(slicer.modules.liverbiopsy.path)
    self.moduleTransformsPath = os.path.join(self.modulePath, 'Resources/Transforms')
    
    self.toolCalibrationMode = self.PIVOT_CALIBRATION

    #TODO remove if tool cal from logic works
#    self.pivotCalibrationLogic = slicer.modules.pivotcalibration.logic()
    self.markupsLogic = slicer.modules.markups.logic()
  
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

    # US Calibration Austria Names
    self.ProbeToUS = self.createVTKMRMLElement('ProbeToUS', 'vtkMRMLLinearTransformNode')
    self.TableToProbe = self.createVTKMRMLElement('TableToProbe', 'vtkMRMLLinearTransformNode')
    self.MRIToTable = self.createVTKMRMLElement('MRIToTable', 'vtkMRMLLinearTransformNode')
    self.ImageToMRI = self.createVTKMRMLElement('ImageToMRI', 'vtkMRMLLinearTransformNode')

    # Setup Stylus Transforms
    self.StylusTipToStylus = self.createVTKMRMLElement('StylusTipToStylus', 'vtkMRMLLinearTransformNode')
    self.StylusBaseToStylus = self.createVTKMRMLElement('StylusBaseToStylus', 'vtkMRMLLinearTransformNode')
          
    # Setup Needle Transforms    
    self.NeedleTipToNeedle = self.createVTKMRMLElement('NeedleTipToNeedle', 'vtkMRMLLinearTransformNode')
    self.NeedleBaseToNeedle = self.createVTKMRMLElement('NeedleBaseToNeedle', 'vtkMRMLLinearTransformNode')

    #Setup CT Transforms
    self.CTToReference = self.createVTKMRMLElement('CTToReference', 'vtkMRMLLinearTransformNode')

    # Set up ReferenceToRas
    # TODO confirm
    self.ReferenceToRas = self.createVTKMRMLElement('ReferenceToRas', 'vtkMRMLLinearTransformNode')
          
    # OpenIGTLink transforms
    self.StylusToReference = slicer.util.getFirstNodeByName('vtkMRMLLinearTransformNode', 'StylusToReference')
    if not self.StylusToReference:
      self.StylusToReference = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'StylusToReference')
      
    self.NeedleToReference = slicer.util.getFirstNodeByName('vtkMRMLLinearTransformNode', 'NeedleToReference')
    if not self.NeedleToReference:
      self.NeedleToReference = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'NeedleToReference')


    # Markups Nodes

    # US Calibration Austria Names
    self.FromProbeToUSFiducialNode = self.createVTKMRMLElement('FromProbeToUSFiducialNode', 'vtkMRMLMarkupsFiducialNode')
    self.ToProbeToUSFiducialNode = self.createVTKMRMLElement('ToProbeToUSFiducialNode', 'vtkMRMLMarkupsFiducialNode')
    self.FromCTToReferenceFiducialNode = self.createVTKMRMLElement('FromCTToReferenceFiducials', 'vtkMRMLMarkupsFiducialNode')
    self.ToCTToReferenceFiducialNode = self.createVTKMRMLElement('ToCTToReferenceFiducials', 'vtkMRMLMarkupsFiducialNode')

    # Build Transform Tree

    # US Calibration Austria Names
    self.TableToProbe.SetAndObserveTransformNodeID(self.ProbeToUS.GetID())
    self.MRIToTable.SetAndObserveTransformNodeID(self.TableToProbe.GetID())
    self.ImageToMRI.SetAndObserveTransformNodeID(self.MRIToTable.GetID())
    self.FromProbeToUSFiducialNode.SetAndObserveTransformNodeID(self.ImageToMRI.GetID())

    self.StylusToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.StylusTipToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.StylusModel_StylusTip.SetAndObserveTransformNodeID(self.StylusTipToStylus.GetID())
    self.StylusBaseToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.NeedleToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.NeedleTipToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.NeedleModel_NeedleTip.SetAndObserveTransformNodeID(self.NeedleTipToNeedle.GetID())
    self.NeedleBaseToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.CTToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())

  def createVTKMRMLElement(self, transformName, vtkMRMLClassName):
    vtkMRMLElement = slicer.util.getFirstNodeByName(transformName, className=vtkMRMLClassName)
    if not vtkMRMLElement:
      fileName = transformName +'.h5'
      vtkMRMLElementPath = os.path.join(self.moduleTransformsPath, fileName)
      try:
        [success,vtkMRMLElement] = slicer.util.loadTransform(vtkMRMLElementPath)
        vtkMRMLElement.SetName(transformName)
        slicer.mrmlScene.AddNode(vtkMRMLElement)
      except:
        logging.debug('Could not load ProbeToUS from file')
        vtkMRMLElement = slicer.mrmlScene.AddNewNodeByClass(vtkMRMLClassName, transformName)

    return vtkMRMLElement


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
    self.toolToReferenceNode = self.StylusToReference
    self.toolBeingCalibrated = 'Stylus'
    self.toolCalibrationToolBaseNode = self.StylusBaseToStylus
    self.toolCalibrationModel = self.StylusModel_StylusTip

    self.ui.needlePivotCalibrationButton.setEnabled(False)
    self.ui.needleSpinCalibrationButton.setEnabled(False)
    self.ui.stylusPivotCalibrationButton.setEnabled(False)
    self.ui.stylusSpinCalibrationButton.setEnabled(False)

    self.toolCalibrationStopTime = time.time() + float(5)
    self.logic.toolCalibration(self.toolToReferenceNode, self.toolCalibrationTimer)


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
    self.toolToReferenceNode = self.NeedleToReference
    self.toolBeingCalibrated = 'Needle'
    self.toolCalibrationToolBaseNode = self.NeedleBaseToNeedle
    self.toolCalibrationModel = self.NeedleModel_NeedleTip
    
    self.ui.needlePivotCalibrationButton.setEnabled(False)
    self.ui.needleSpinCalibrationButton.setEnabled(False)
    self.ui.stylusPivotCalibrationButton.setEnabled(False)
    self.ui.stylusSpinCalibrationButton.setEnabled(False)

    self.toolCalibrationStopTime = time.time() + float(5)
    self.logic.toolCalibration(self.toolToReferenceNode, self.toolCalibrationTimer)


  def toolCalibrationTimeout(self):
    logging.debug('toolCalibrationTimeout')
    
    if self.toolBeingCalibrated == 'Needle':
      self.ui.needleCalibrationErrorLabel.setText("")
      self.ui.needleCalibrationCountdownLabel.setText("Calibrating for {0:.0f} more seconds".format(self.toolCalibrationStopTime - time.time()))
    elif self.toolBeingCalibrated == 'Stylus':
      self.ui.stylusCalibrationErrorLabel.setText("")
      self.ui.stylusCalibrationCountdownLabel.setText("Calibrating for {0:.0f} more seconds".format(self.toolCalibrationStopTime - time.time()))
    
    if (time.time() >= self.toolCalibrationStopTime):
      self.toolCalibrationTimer.stop()

      self.ui.needlePivotCalibrationButton.setEnabled(True)
      self.ui.needleSpinCalibrationButton.setEnabled(True)
      self.ui.stylusPivotCalibrationButton.setEnabled(True)
      self.ui.stylusSpinCalibrationButton.setEnabled(True)

      # calibration completed
      if self.toolCalibrationMode == self.PIVOT_CALIBRATION:

        calibrationStatus, calibrationError, toolLength = self.logic.pivotCalibratiion( self.calibrationErrorThresholdMm, self.toolCalibrationResultNode, self.toolCalibrationToolBaseNode)

        self.updateDisplayedToolLength(toolLength)

        if self.toolBeingCalibrated == 'Needle':
          self.ui.needleCalibrationErrorLabel.setText(calibrationStatus)
          self.ui.needleCalibrationCountdownLabel.setText(calibrationError)
        else:
          self.ui.stylusCalibrationErrorLabel.setText(calibrationStatus)
          self.ui.stylusCalibrationCountdownLabel.setText(calibrationError)
      else:
        calibrationStatus, calibrationError = self.logic.spinCalibratiion(self.calibrationErrorThresholdMm, self.toolCalibrationResultNode)

        if self.toolBeingCalibrated == 'Needle':
          self.ui.needleCalibrationErrorLabel.setText(calibrationStatus)
          self.ui.needleCalibrationCountdownLabel.setText(calibrationError)
        else:
          self.ui.stylusCalibrationErrorLabel.setText(calibrationStatus)
          self.ui.stylusCalibrationCountdownLabel.setText(calibrationError)

  def updateDisplayedToolLength(self, toolLength):
    logging.debug("updateDisplayedToolLength")
    # Update the needle model
    slicer.modules.createmodels.logic().CreateNeedle(toolLength,1.0, 1.5, False, self.toolCalibrationModel)


  def returnPointAtStylusTip(self): #Coordinate returned is in the reference coordinate system
    logging.debug('returnPointAtStylusTip')
    StylusTipToReference = vtk.vtkMatrix4x4()

    self.StylusTipToStylus.GetMatrixTransformToWorld(StylusTipToReference)
    return [StylusTipToReference.GetElement(0,3), StylusTipToReference.GetElement(1,3), StylusTipToReference.GetElement(2,3)]


  def returnTransformedPointAtStylusTip(self, TargetTransform): #Coordinate returned is in target coordinate system
    logging.debug('returnTransformedPointAtStylusTip')
    StylusTipToTarget = vtk.vtkMatrix4x4()

    self.StylusTipToStylus.GetMatrixTransformToNode(TargetTransform, StylusTipToTarget)
    
    return [StylusTipToTarget.GetElement(0,3), StylusTipToTarget.GetElement(1,3), StylusTipToTarget.GetElement(2,3)]


  def USCalibration(self):
    logging.debug("USCalibration")
    
    fromMarkupsNode = self.ui.fromProbeToUSFiducialWidget.currentNode()
    toMarkupsNode = self.ui.toProbeToUSFiducialWidget.currentNode()
    outputTransformNode = self.ProbeToUS
    
    calibrationMessage, RMSE = self.logic.landmarkRegistration(fromMarkupsNode, toMarkupsNode, outputTransformNode)

    self.ui.USCalibrationErrorLabel.setText(calibrationMessage.format(RMSE))


  def placeToCTToReferenceFiducial(self):
    logging.debug("placeToCTToReferenceFiducial")
    
    currentNode = self.ui.toCTToReferenceFiducialWidget.currentNode()
    
    self.markupsLogic.SetActiveListID(currentNode)
    newFiducial = self.returnPointAtStylusTip()
    
    currentNode.AddFiducialFromArray(newFiducial)


  def initialCTRegistration(self):
    logging.debug("initialCTRegistration")
    
    fromMarkupsNode = self.ui.fromCTToReferenceFiducialWidget.currentNode()
    toMarkupsNode = self.ui.toCTToReferenceFiducialWidget.currentNode()
    outputTransformNode = self.CTToReference
    
    calibrationMessage, RMSE = self.logic.landmarkRegistration(fromMarkupsNode, toMarkupsNode, outputTransformNode)

    self.ui.initialCTRegistrationErrorLabel.setText(calibrationMessage.format(RMSE))


  def saveTransforms(self):
    logging.debug("saveTransforms")
    
    slicer.util.saveNode(self.StylusTipToStylus, os.path.join(self.moduleTransformsPath, 'StylusTipToStylus' + ".h5"))
    slicer.util.saveNode(self.NeedleTipToNeedle, os.path.join(self.moduleTransformsPath, 'NeedleTipToNeedle' + ".h5"))
    slicer.util.saveNode(self.ReferenceToRas, os.path.join(self.moduleTransformsPath, 'ReferenceToRas' + ".h5"))
    slicer.util.saveNode(self.CTToReference, os.path.join(self.moduleTransformsPath, 'CTToReference' + ".h5"))
    slicer.util.saveNode(self.ProbeToUS, os.path.join(self.moduleTransformsPath, 'ProbeToUS' + ".h5"))


  def onFreezeUltrasound(self):
    logging.debug("onFreezeUltrasound")

    buttonLabel = self.ui.freezeUltrasoundButton.text
    if buttonLabel == 'Freeze Ultrasound':
      self.ui.freezeUltrasoundButton.setText('Unfreeze Ultrasound')

      self.UltrasoundVolumeNode = slicer.util.getFirstNodeByName('Ultrasound_Ultrasound')
      self.FrozenUS = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeDisplayNode', 'FrozenUltrasound')


    else:
      self.ui.freezeUltrasoundButton.setText('Freeze Ultrasound')


  def onTestFunction(self):
    pass


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

  def toolCalibration(self, transformNodeToolToReference, qtTimer):
    logging.debug('toolCalibration')

    self.pivotCalibrationLogic = slicer.modules.pivotcalibration.logic()
    self.pivotCalibrationLogic.SetAndObserveTransformNode(transformNodeToolToReference)

    qtTimer.start()
    self.pivotCalibrationLogic.SetRecordingState(True)

  def pivotCalibration(self, calibrationErrorThresholdMm, toolCalibrationResultNode, toolCalibrationToolBaseNode):
    logging.debug('pivotCalibration')

    self.pivotCalibrationLogic.SetRecordingState(False)

    calibrationSuccess = self.pivotCalibrationLogic.ComputePivotCalibration()
    if not calibrationSuccess:
      self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
      return "Calibration failed: ", self.pivotCalibrationLogic.GetErrorText(), 0
    else:
      if (self.pivotCalibrationLogic.GetPivotRMSE() >= float(calibrationErrorThresholdMm)):
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        return "Calibration failed:", "Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetPivotRMSE()), 0
      else:
        toolTipToToolMatrix = vtk.vtkMatrix4x4()
        self.pivotCalibrationLogic.GetToolTipToToolMatrix(toolTipToToolMatrix)
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        toolCalibrationResultNode.SetMatrixTransformToParent(toolTipToToolMatrix)

        toolTipToToolBaseTransform = vtk.vtkMatrix4x4()
        toolCalibrationResultNode.GetMatrixTransformToNode(toolCalibrationToolBaseNode, toolTipToToolBaseTransform)
        toolLength = int(math.sqrt(toolTipToToolBaseTransform.GetElement(0, 3) ** 2 + toolTipToToolBaseTransform.GetElement(1,3) ** 2 + toolTipToToolBaseTransform.GetElement(2, 3) ** 2))

        return "Calibration completed", "Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetPivotRMSE()), toolLength


  def spinCalibration(self, calibrationErrorThresholdMm, toolCalibrationResultNode):
    logging.debug('spinCalibration')

    self.pivotCalibrationLogic.SetRecordingState(False)

    calibrationSuccess = self.pivotCalibrationLogic.ComputeSpinCalibration()
    if not calibrationSuccess:
      self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
      return "Calibration failed: ", self.pivotCalibrationLogic.GetErrorText()
    else:
      if (self.pivotCalibrationLogic.GetSpinRMSE() >= float(calibrationErrorThresholdMm)):
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        return "Calibration failed:", "Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetSpinRMSE())
      else:
        toolTipToToolMatrix = vtk.vtkMatrix4x4()
        self.pivotCalibrationLogic.GetToolTipToToolMatrix(toolTipToToolMatrix)
        self.pivotCalibrationLogic.ClearToolToReferenceMatrices()
        toolCalibrationResultNode.SetMatrixTransformToParent(toolTipToToolMatrix)

        return "Calibration completed", "Error = {0:.2f} mm".format(self.pivotCalibrationLogic.GetSpinRMSE())
  
  def landmarkRegistration(self, fromMarkupsNode, toMarkupsNode, outputTransformNode):
    logging.debug('landmarkRegistration')
    
    fromPoints = vtk.vtkPoints()
    toPoints = vtk.vtkPoints()

    nFromPoints = fromMarkupsNode.GetNumberOfFiducials()
    nToPoints = toMarkupsNode.GetNumberOfFiducials()
    
    if nFromPoints != nToPoints:
      return 'Number of points in markups nodes are not equal. Error {0:.2f}', 1
      
    if nFromPoints < 3:
      return 'Insufficient number of points in markups nodes. Error {0:.2f}', 2

    for i in range( nFromPoints ):
      p = [0, 0, 0]
      fromMarkupsNode.GetNthControlPointPositionWorld(i, p)
      fromPoints.InsertNextPoint( p )
      toMarkupsNode.GetNthControlPointPositionWorld(i, p)
      toPoints.InsertNextPoint( p )

    lt = vtk.vtkLandmarkTransform()
    lt.SetSourceLandmarks( fromPoints )
    lt.SetTargetLandmarks( toPoints )
    lt.SetModeToSimilarity()
    lt.Update()

    resultsMatrix = vtk.vtkMatrix4x4()
    lt.GetMatrix( resultsMatrix )

    det = resultsMatrix.Determinant()
    if det < 1e-8:
      return 'Unstable registration. Check input for collinear points. Error {0:.2f}', 3
      
    outputTransformNode.SetMatrixTransformToParent(resultsMatrix)
    
    return self.calculateRMSE(nFromPoints, fromPoints, toPoints, resultsMatrix)
    
  def calculateRMSE(self, nPoints, fromPoints, toPoints, transformMatrix):
    logging.debug('calculateRMSE')
    sumSquareError = 0
    
    for i in range( nPoints ):
      pFrom = fromPoints.GetPoint(i)
      pTo = toPoints.GetPoint(i)

      pFrom = [pFrom[0], pFrom[1], pFrom[2], 1]
      transformMatrix.MultiplyPoint(pFrom, pFrom)
      
      dist = (pTo[0] - pFrom[0]) ** 2 + (pTo[1] - pFrom[1]) ** 2 + (pTo[2] - pFrom[2]) ** 2
      sumSquareError += dist
    
    RMSE = math.sqrt(sumSquareError/nPoints)
    
    return "Success. Error = {0:.2f} mm", RMSE


  def calculateSubtransform(self, AToCTransformNode, BToCTransformNode, outputTransformNode):
    logging.debug('calculateSubtransform')
    # In a transform hierarchy with A -> B -> C 
    # This function calculates the transform A -> B given the transforms B -> C and A -> C 
    AToCMatrix = vtk.vtkMatrix4x4()
    
    
    CToBMatrix = vtk.vtkMatrix4x4()
    
    resultsMatrix = vtk.vtkMatrix4x4()
    resultsMatrix.Multiply4x4(CToBMatrix, AToCMatrix)
    
    outputTransformNode.SetMatrixTransformToParent(resultsMatrix)
    return


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
