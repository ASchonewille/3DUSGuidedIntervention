import os, time, math
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# AbdominalBiopsyNavigation
#

class AbdominalBiopsyNavigation(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "AbdominalBiopsyNavigation"
    self.parent.categories = ["US Guided Intervention"]
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Abigael Schonewille (PerkLab)"]
    self.parent.helpText = """
This is a module designed to be the framework for abdominal percutaneous interventions guided by 3D ultrasound. 
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()  # TODO: verify that the default URL is correct or change it to the actual documentation
    self.parent.acknowledgementText = """
"""  # TODO: replace with organization, grant and thanks.

#
# AbdominalBiopsyNavigationWidget
#

class AbdominalBiopsyNavigationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None

    # Class Parameters
    self.calibrationErrorThresholdMm = 0.9
    self.PIVOT_CALIBRATION = 0
    self.SPIN_CALIBRATION = 1

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """

    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/AbdominalBiopsyNavigation.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Set up slicer scene
    self.setupScene()
    self.setupCustomViews()

    # Create a new parameterNode
    # This parameterNode stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.logic = AbdominalBiopsyNavigationLogic()
    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Dependencies
    self.markupsLogic = slicer.modules.markups.logic()

    # Connections
    self.ui.parameterNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setParameterNode)

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

    # Default widget settings
    self.toolCalibrationTimer = qt.QTimer()
    self.toolCalibrationTimer.setInterval(500)
    self.toolCalibrationTimer.connect('timeout()', self.toolCalibrationTimeout)

    self.ui.fromProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromProbeToUSFiducialWidget.setNodeColor(qt.QColor(207, 26, 0, 255))
    self.ui.toProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toProbeToUSFiducialWidget.setNodeColor(qt.QColor(103, 0, 225, 255))

    self.ui.fromCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromCTToReferenceFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromCTToReferenceFiducialWidget.setNodeColor(qt.QColor(85, 255, 0, 255))
    self.ui.toCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToCTToReferenceFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toCTToReferenceFiducialWidget.setNodeColor(qt.QColor(255, 170, 0, 255))

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.fromCTToReferenceFiducialWidget.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.toCTToReferenceFiducialWidget.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.fromProbeToUSFiducialWidget.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.toProbeToUSFiducialWidget.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Initial GUI update
    self.updateGUIFromParameterNode()


  def setupScene(self):

    self.modulePath = os.path.dirname(slicer.modules.abdominalbiopsynavigation.path)
    self.moduleTransformsPath = os.path.join(self.modulePath, 'Resources/Transforms')

    self.toolCalibrationMode = self.PIVOT_CALIBRATION

    # Models
    self.StylusModel_StylusTip = slicer.util.getFirstNodeByName('StylusModel', 'vtkMRMLModelNode')
    if not self.StylusModel_StylusTip:
      slicer.modules.createmodels.logic().CreateNeedle(60, 1.0, 1.5, 0)
      self.StylusModel_StylusTip = slicer.util.getFirstNodeByName("NeedleModel", 'vtkMRMLModelNode')
      self.StylusModel_StylusTip.GetDisplayNode().SetColor(0.33, 1.0, 1.0)
      self.StylusModel_StylusTip.SetName("StylusModel")
      self.StylusModel_StylusTip.GetDisplayNode().SliceIntersectionVisibilityOn()
    self.StylusModel_StylusTip.GetDisplayNode().SetColor(0, 1, 1)

    self.NeedleModel_NeedleTip = slicer.util.getFirstNodeByName('NeedleModel', 'vtkMRMLModelNode')
    if not self.NeedleModel_NeedleTip:
      slicer.modules.createmodels.logic().CreateNeedle(60, 1.0, 1.5, 0)
      self.NeedleModel_NeedleTip = slicer.util.getFirstNodeByName("NeedleModel", 'vtkMRMLModelNode')
      self.NeedleModel_NeedleTip.GetDisplayNode().SetColor(0.33, 1.0, 1.0)
      self.NeedleModel_NeedleTip.SetName("NeedleModel")
      self.NeedleModel_NeedleTip.GetDisplayNode().SliceIntersectionVisibilityOn()
    self.NeedleModel_NeedleTip.GetDisplayNode().SetColor(1, 1, 0)

    # Transforms

    # US Calibration Austria Names
    self.ProbeToUS = self.createVTKMRMLElement('ProbeToUS', 'vtkMRMLLinearTransformNode')
    self.TableToProbe = self.createVTKMRMLElement('TableToProbe', 'vtkMRMLLinearTransformNode')
    self.MRIToTable = self.createVTKMRMLElement('MRIToTable', 'vtkMRMLLinearTransformNode')
    self.ImageToMRI = self.createVTKMRMLElement('ImageToMRI', 'vtkMRMLLinearTransformNode')
    self.ProbeToReference = self.createVTKMRMLElement('ProbeToReference', 'vtkMRMLLinearTransformNode')
    self.USToProbe = self.createVTKMRMLElement('USToProbe', 'vtkMRMLLinearTransformNode')


    # Setup Stylus Transforms
    self.StylusTipToStylus = self.createVTKMRMLElement('StylusTipToStylus', 'vtkMRMLLinearTransformNode')

    # Setup Needle Transforms
    self.NeedleTipToNeedle = self.createVTKMRMLElement('NeedleTipToNeedle', 'vtkMRMLLinearTransformNode')

    # Setup CT Transforms
    self.CTToReference = self.createVTKMRMLElement('CTToReference', 'vtkMRMLLinearTransformNode')

    # Set up ReferenceToRas
    # TODO confirm
    self.ReferenceToRas = self.createVTKMRMLElement('ReferenceToRas', 'vtkMRMLLinearTransformNode')

    # OpenIGTLink transforms
    self.StylusToReference = self.createVTKMRMLElement('StylusToReference', 'vtkMRMLLinearTransformNode')

    self.NeedleToReference = self.createVTKMRMLElement('NeedleToReference', 'vtkMRMLLinearTransformNode')

    # Markups Nodes

    # US Calibration Austria Names
    self.FromProbeToUSFiducialNode = self.createVTKMRMLElement('FromProbeToUSFiducialNode', 'vtkMRMLMarkupsFiducialNode')
    self.ToProbeToUSFiducialNode = self.createVTKMRMLElement('ToProbeToUSFiducialNode', 'vtkMRMLMarkupsFiducialNode')
    self.FromCTToReferenceFiducialNode = self.createVTKMRMLElement('FromCTToReferenceFiducialNode', 'vtkMRMLMarkupsFiducialNode')
    self.ToCTToReferenceFiducialNode = self.createVTKMRMLElement('ToCTToReferenceFiducialNode', 'vtkMRMLMarkupsFiducialNode')

    # Build Transform Tree

    # US Calibration Austria Names
    self.TableToProbe.SetAndObserveTransformNodeID(self.ProbeToUS.GetID())
    self.MRIToTable.SetAndObserveTransformNodeID(self.TableToProbe.GetID())
    self.ImageToMRI.SetAndObserveTransformNodeID(self.MRIToTable.GetID())
    self.FromProbeToUSFiducialNode.SetAndObserveTransformNodeID(self.ImageToMRI.GetID())

    self.StylusToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.StylusTipToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.StylusModel_StylusTip.SetAndObserveTransformNodeID(self.StylusTipToStylus.GetID())
    self.NeedleToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.NeedleTipToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.NeedleModel_NeedleTip.SetAndObserveTransformNodeID(self.NeedleTipToNeedle.GetID())
    self.CTToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.ProbeToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.USToProbe.SetAndObserveTransformNodeID(self.ProbeToReference.GetID())
    self.FromCTToReferenceFiducialNode.SetAndObserveTransformNodeID(self.CTToReference.GetID())
    self.ToCTToReferenceFiducialNode.SetAndObserveTransformNodeID(self.USToProbe.GetID()) # TODO: Change to be under StylusTipToStylus for real protocol

  def createVTKMRMLElement(self, transformName, vtkMRMLClassName):
    vtkMRMLElement = slicer.util.getFirstNodeByName(transformName, className=vtkMRMLClassName)
    if not vtkMRMLElement:
      fileName = transformName + '.h5'
      vtkMRMLElementPath = os.path.join(self.moduleTransformsPath, fileName)
      try:
        [success, vtkMRMLElement] = slicer.util.loadTransform(vtkMRMLElementPath)
        vtkMRMLElement.SetName(transformName)
        slicer.mrmlScene.AddNode(vtkMRMLElement)
      except:
        logging.debug('Could not load ProbeToUS from file')
        vtkMRMLElement = slicer.mrmlScene.AddNewNodeByClass(vtkMRMLClassName, transformName)

    return vtkMRMLElement

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def setParameterNode(self, inputParameterNode):
    """
    Adds observers to the selected parameter node. Observation is needed because when the
    parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Set parameter node in the parameter node selector widget
    wasBlocked = self.ui.parameterNodeSelector.blockSignals(True)
    self.ui.parameterNodeSelector.setCurrentNode(inputParameterNode)
    self.ui.parameterNodeSelector.blockSignals(wasBlocked)

    if inputParameterNode == self._parameterNode:
      # No change
      return

    # Unobserve previusly selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if inputParameterNode is not None:
      self.addObserver(inputParameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    # Disable all sections if no parameter node is selected
    self.ui.CTRegistrationBox.enabled = self._parameterNode is not None
    self.ui.ConnectPLUSBox.enabled = self._parameterNode is not None
    self.ui.NavigationBox.enabled = self._parameterNode is not None
    self.ui.SettingsBox.enabled = self._parameterNode is not None
    self.ui.ToolCalibrationBox.enabled = self._parameterNode is not None
    self.ui.USToUSCalibrationBox.enabled = self._parameterNode is not None
    if self._parameterNode is None:
      return

    # Update each widget from parameter node
    # Need to temporarily block signals to prevent infinite recursion (MRML node update triggers
    # GUI update, which triggers MRML node update, which triggers GUI update, ...)
    # TODO add all ui elements that update mrml node
    wasBlocked = self.ui.fromCTToReferenceFiducialWidget.blockSignals(True)
    self.ui.fromCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName(self._parameterNode.GetParameter("FromCTToReferenceFiducialNode"), className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromCTToReferenceFiducialWidget.blockSignals(wasBlocked)

    wasBlocked = self.ui.toCTToReferenceFiducialWidget.blockSignals(True)
    self.ui.toCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName(self._parameterNode.GetParameter("ToCTToReferenceFiducialNode"), className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toCTToReferenceFiducialWidget.blockSignals(wasBlocked)

    wasBlocked = self.ui.fromProbeToUSFiducialWidget.blockSignals(True)
    self.ui.fromProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName(self._parameterNode.GetParameter("FromProbeToUSFiducialNode"), className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromProbeToUSFiducialWidget.blockSignals(wasBlocked)

    wasBlocked = self.ui.toProbeToUSFiducialWidget.blockSignals(True)
    self.ui.toProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName(self._parameterNode.GetParameter("ToProbeToUSFiducialNode"), className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toProbeToUSFiducialWidget.blockSignals(wasBlocked)

    # Update buttons states and tooltips

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None:
      return

    self._parameterNode.SetParameter("FromCTToReferenceFiducialNode", self.ui.fromCTToReferenceFiducialWidget.currentNode.GetName())
    self._parameterNode.SetParameter("ToCTToReferenceFiducialNode", self.ui.toCTToReferenceFiducialWidget.currentNode.GetName())
    self._parameterNode.SetParameter("FromProbeToUSFiducialNode", self.ui.fromProbeToUSFiducialWidget.currentNode.GetName())
    self._parameterNode.SetParameter("ToProbeToUSFiducialNode", self.ui.toProbeToUSFiducialWidget.currentNode.GetName())

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

    RGBO3DLayoutID = 400

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

    if (view == "Conventional View"):
      requestedID = 2
    elif (view == "Red Slice View"):
      requestedID = 6
    elif (view == "RGBO3D View"):
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
      self.ui.needleCalibrationCountdownLabel.setText(
        "Calibrating for {0:.0f} more seconds".format(self.toolCalibrationStopTime - time.time()))
    elif self.toolBeingCalibrated == 'Stylus':
      self.ui.stylusCalibrationErrorLabel.setText("")
      self.ui.stylusCalibrationCountdownLabel.setText(
        "Calibrating for {0:.0f} more seconds".format(self.toolCalibrationStopTime - time.time()))

    if (time.time() >= self.toolCalibrationStopTime):
      self.toolCalibrationTimer.stop()

      self.ui.needlePivotCalibrationButton.setEnabled(True)
      self.ui.needleSpinCalibrationButton.setEnabled(True)
      self.ui.stylusPivotCalibrationButton.setEnabled(True)
      self.ui.stylusSpinCalibrationButton.setEnabled(True)

      # calibration completed
      if self.toolCalibrationMode == self.PIVOT_CALIBRATION:

        calibrationStatus, calibrationError, toolLength = self.logic.pivotCalibration(self.calibrationErrorThresholdMm, self.toolCalibrationResultNode)

        self.updateDisplayedToolLength(toolLength)

        if self.toolBeingCalibrated == 'Needle':
          self.ui.needleCalibrationErrorLabel.setText(calibrationError)
          self.ui.needleCalibrationCountdownLabel.setText(calibrationStatus)
        else:
          self.ui.stylusCalibrationErrorLabel.setText(calibrationError)
          self.ui.stylusCalibrationCountdownLabel.setText(calibrationStatus)
      else:
        calibrationStatus, calibrationError = self.logic.spinCalibration(self.calibrationErrorThresholdMm, self.toolCalibrationResultNode)

        if self.toolBeingCalibrated == 'Needle':
          self.ui.needleCalibrationErrorLabel.setText(calibrationError)
          self.ui.needleCalibrationCountdownLabel.setText(calibrationStatus)
        else:
          self.ui.stylusCalibrationErrorLabel.setText(calibrationError)
          self.ui.stylusCalibrationCountdownLabel.setText(calibrationStatus)

  def updateDisplayedToolLength(self, toolLength):
    logging.debug("updateDisplayedToolLength")
    # Update the needle model
    slicer.modules.createmodels.logic().CreateNeedle(toolLength, 1.0, 1.5, False, self.toolCalibrationModel)

  def returnPointAtStylusTip(self):  # Coordinate returned is in the reference coordinate system
    logging.debug('returnPointAtStylusTip')
    StylusTipToReference = vtk.vtkMatrix4x4()

    self.StylusTipToStylus.GetMatrixTransformToWorld(StylusTipToReference)
    return [StylusTipToReference.GetElement(0, 3), StylusTipToReference.GetElement(1, 3),
            StylusTipToReference.GetElement(2, 3)]

  def returnTransformedPointAtStylusTip(self, TargetTransform):  # Coordinate returned is in target coordinate system
    logging.debug('returnTransformedPointAtStylusTip')
    StylusTipToTarget = vtk.vtkMatrix4x4()

    self.StylusTipToStylus.GetMatrixTransformToNode(TargetTransform, StylusTipToTarget)

    return [StylusTipToTarget.GetElement(0, 3), StylusTipToTarget.GetElement(1, 3), StylusTipToTarget.GetElement(2, 3)]

  def USCalibration(self):
    logging.debug("USCalibration")

    fromMarkupsNode = self.ui.fromProbeToUSFiducialWidget.currentNode()
    toMarkupsNode = self.ui.toProbeToUSFiducialWidget.currentNode()
    outputTransformNode = self.ProbeToUS

    calibrationMessage, RMSE = self.logic.landmarkRegistration(fromMarkupsNode, toMarkupsNode, outputTransformNode)

    self.USToProbe.SetMatrixTransformToParent(self.ProbeToUS.GetMatrixTransformFromParent())
    self.USToProbe.Inverse()

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


#
# AbdominalBiopsyNavigationLogic
#

class AbdominalBiopsyNavigationLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("FromCTToReferenceFiducialNode"):
      parameterNode.SetParameter("FromCTToReferenceFiducialNode", "FromCTToReferenceFiducialNode")
    if not parameterNode.GetParameter("ToCTToReferenceFiducialNode"):
      parameterNode.SetParameter("ToCTToReferenceFiducialNode", "ToCTToReferenceFiducialNode")
    if not parameterNode.GetParameter("FromProbeToUSFiducialNode"):
      parameterNode.SetParameter("FromProbeToUSFiducialNode", "FromProbeToUSFiducialNode")
    if not parameterNode.GetParameter("ToProbeToUSFiducialNode"):
      parameterNode.SetParameter("ToProbeToUSFiducialNode", "ToProbeToUSFiducialNode")

  def toolCalibration(self, transformNodeToolToReference, qtTimer):
    logging.debug('toolCalibration')

    self.pivotCalibrationLogic = slicer.modules.pivotcalibration.logic()
    self.pivotCalibrationLogic.SetAndObserveTransformNode(transformNodeToolToReference)

    qtTimer.start()
    self.pivotCalibrationLogic.SetRecordingState(True)

  def pivotCalibration(self, calibrationErrorThresholdMm, toolCalibrationResultNode):
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

        return "Calibration completed", "Error = {0:.2f} mm".format(
          self.pivotCalibrationLogic.GetPivotRMSE()), toolLength

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

    for i in range(nFromPoints):
      p = [0, 0, 0]
      fromMarkupsNode.GetNthControlPointPositionWorld(i, p)
      fromPoints.InsertNextPoint(p)
      toMarkupsNode.GetNthControlPointPositionWorld(i, p)
      toPoints.InsertNextPoint(p)

    lt = vtk.vtkLandmarkTransform()
    lt.SetSourceLandmarks(fromPoints)
    lt.SetTargetLandmarks(toPoints)
    lt.SetModeToSimilarity()
    lt.Update()

    resultsMatrix = vtk.vtkMatrix4x4()
    lt.GetMatrix(resultsMatrix)

    det = resultsMatrix.Determinant()
    if det < 1e-8:
      return 'Unstable registration. Check input for collinear points. Error {0:.2f}', 3

    outputTransformNode.SetMatrixTransformToParent(resultsMatrix)

    return self.calculateRMSE(nFromPoints, fromPoints, toPoints, resultsMatrix)

  def calculateRMSE(self, nPoints, fromPoints, toPoints, transformMatrix):
    logging.debug('calculateRMSE')
    sumSquareError = 0

    for i in range(nPoints):
      pFrom = fromPoints.GetPoint(i)
      pTo = toPoints.GetPoint(i)

      pFrom = [pFrom[0], pFrom[1], pFrom[2], 1]
      transformMatrix.MultiplyPoint(pFrom, pFrom)

      dist = (pTo[0] - pFrom[0]) ** 2 + (pTo[1] - pFrom[1]) ** 2 + (pTo[2] - pFrom[2]) ** 2
      sumSquareError += dist

    RMSE = math.sqrt(sumSquareError / nPoints)

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

#
# AbdominalBiopsyNavigationTest
#

class AbdominalBiopsyNavigationTest(ScriptedLoadableModuleTest):
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
    self.test_AbdominalBiopsyNavigation1()

  def test_AbdominalBiopsyNavigation1(self):
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

    # Get/create input data

    import SampleData
    inputVolume = SampleData.downloadFromURL(
      nodeNames='MRHead',
      fileNames='MR-Head.nrrd',
      uris='https://github.com/Slicer/SlicerTestingData/releases/download/MD5/39b01631b7b38232a220007230624c8e',
      checksums='MD5:39b01631b7b38232a220007230624c8e')[0]
    self.delayDisplay('Finished with download and loading')

    inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    self.assertEqual(inputScalarRange[0], 0)
    self.assertEqual(inputScalarRange[1], 279)

    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    threshold = 50

    # Test the module logic

    logic = AbdominalBiopsyNavigationLogic()

    # Test algorithm with non-inverted threshold
    logic.run(inputVolume, outputVolume, threshold, True)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], threshold)

    # Test algorithm with inverted threshold
    logic.run(inputVolume, outputVolume, threshold, False)
    outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    self.assertEqual(outputScalarRange[1], inputScalarRange[1])

    self.delayDisplay('Test passed')
