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
#    self.ui.fromUSToReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)
#    self.ui.toUSToReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.fromCTToReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.toCTToReferenceFiducialWidget.setMRMLScene(slicer.mrmlScene)

    # connections
    self.ui.FineCTRegistrationBox.connect('clicked(bool)', self.changeCollapsedView("FineCTRegistrationBox"))
    self.ui.InitialCTRegistrationBox.connect('clicked(bool)', self.changeCollapsedView("InitialCTRegistrationBox"))
    self.ui.NavigationBox.connect('clicked(bool)', self.changeCollapsedView("NavigationBox"))
    self.ui.NeedleCalibrationBox.connect('clicked(bool)', self.changeCollapsedView("NeedleCalibrationBox"))
    self.ui.ProbeCalibrationBox.connect('clicked(bool)', self.changeCollapsedView("ProbeCalibrationBox"))
    self.ui.SettingsBox.connect('clicked(bool)', self.changeCollapsedView("SettingsBox"))
    self.ui.StylusCalibrationBox.connect('clicked(bool)', self.changeCollapsedView("StylusCalibrationBox"))
    self.ui.ConnectPLUSBox.connect('clicked(bool)', self.changeCollapsedView("ConnectPLUSBox"))
    
    self.ui.saveButton.connect('clicked(bool)', self.onSaveScene)
    self.ui.connectPLUSButton.connect('clicked(bool)', self.onConnectPLUS)
    self.ui.layoutComboBox.connect('activated(const QString &)', self.onChangeLayout)
    self.ui.needleSpinCalibrationButton.connect('clicked(bool)', self.needleSpinCalibration)
    self.ui.needlePivotCalibrationButton.connect('clicked(bool)', self.needlePivotCalibration)
    self.ui.stylusSpinCalibrationButton.connect('clicked(bool)', self.stylusSpinCalibration)
    self.ui.stylusPivotCalibrationButton.connect('clicked(bool)', self.stylusPivotCalibration)
    self.ui.USCalibrationButton.connect('clicked(bool)', self.USCalibration)
#    self.ui.placeToUSToReferenceFiducialButton.connect('clicked(bool)', self.placeToUSToReferenceFiducial)
    self.ui.initialCTRegistrationButton.connect('clicked(bool)', self.initialCTRegistration)
    self.ui.placeToCTToReferenceFiducialButton.connect('clicked(bool)', self.placeToCTToReferenceFiducial)
    
    self.toolCalibrationTimer = qt.QTimer()
    self.toolCalibrationTimer.setInterval(500)
    self.toolCalibrationTimer.setSingleShot(True)
    self.toolCalibrationTimer.connect('timeout()', self.toolCalibrationTimeout)

    self.ui.fromProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromProbeToUSFiducialWidget.setNodeColor(qt.QColor(207,26,0,255))
    self.ui.toProbeToUSFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toProbeToUSFiducialWidget.setNodeColor(qt.QColor(103,0,225,255))
#    self.ui.fromUSToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromUSToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
#    self.ui.fromUSToReferenceFiducialWidget.setNodeColor(qt.QColor(207,26,0,255))
#    self.ui.toUSToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToUSToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
#    self.ui.toUSToReferenceFiducialWidget.setNodeColor(qt.QColor(103,0,225,255))
    
    self.ui.fromCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('FromCTToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.fromCTToReferenceFiducialWidget.setNodeColor(qt.QColor(85,255,0,255))
    self.ui.toCTToReferenceFiducialWidget.setCurrentNode(slicer.util.getFirstNodeByName('ToCTToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode'))
    self.ui.toCTToReferenceFiducialWidget.setNodeColor(qt.QColor(255,170,0,255))
    
    self.ui.testButton.connect('clicked(bool)', self.onTestFunction)
    
    # Add vertical spacer
    self.layout.addStretch(1)


  def setupScene(self):
    self.PIVOT_CALIBRATION = 0
    self.SPIN_CALIBRATION = 1
    
    self.modulePath = os.path.dirname(slicer.modules.liverbiopsy.path)
    self.moduleTransformsPath = os.path.join(self.modulePath, 'Resources/Transforms')
    
    self.toolCalibrationMode = self.PIVOT_CALIBRATION
    
    self.pivotCalibrationLogic = slicer.modules.pivotcalibration.logic()
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
    self.ProbeToUS = slicer.util.getFirstNodeByName('ProbeToUS', className='vtkMRMLLinearTransformNode')
    if not self.ProbeToUS:
      self.ProbeToUSFilePath = os.path.join(self.moduleTransformsPath, 'ProbeToUS.h5')
      [success, self.ProbeToUS] = slicer.util.loadTransform(self.ProbeToUSFilePath, returnNode = True)
      if success == True:
        self.ProbeToUS.SetName("ProbeToUS")
        slicer.mrmlScene.AddNode(self.ProbeToUS)
      else:
        logging.debug('Could not load ProbeToUS from file')
        self.ProbeToUS = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'ProbeToUS')
        if not self.ProbeToUS:
          logging.debug('Failed: Creation of ProbeToUS transform')
        else:
          logging.debug('Creation of ProbeToUS transform')

    self.TableToProbe = slicer.util.getFirstNodeByName('TableToProbe', className='vtkMRMLLinearTransformNode')
    if not self.TableToProbe:
      self.TableToProbeFilePath = os.path.join(self.moduleTransformsPath, 'TableToProbe.h5')
      [success, self.TableToProbe] = slicer.util.loadTransform(self.TableToProbeFilePath, returnNode=True)
      if success == True:
        self.TableToProbe.SetName("TableToProbe")
        slicer.mrmlScene.AddNode(self.TableToProbe)
      else:
        logging.debug('Could not load TableToProbe from file')
        self.TableToProbe = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'TableToProbe')
        if not self.TableToProbe:
          logging.debug('Failed: Creation of TableToProbe transform')
        else:
          logging.debug('Creation of TableToProbe transform')

    self.MRIToTable = slicer.util.getFirstNodeByName('MRIToTable', className='vtkMRMLLinearTransformNode')
    if not self.MRIToTable:
      self.MRIToTableFilePath = os.path.join(self.moduleTransformsPath, 'MRIToTable.h5')
      [success, self.MRIToTable] = slicer.util.loadTransform(self.MRIToTableFilePath, returnNode=True)
      if success == True:
        self.MRIToTable.SetName("MRIToTable")
        slicer.mrmlScene.AddNode(self.MRIToTable)
      else:
        logging.debug('Could not load MRIToTable from file')
        self.MRIToTable = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'MRIToTable')
        if not self.MRIToTable:
          logging.debug('Failed: Creation of MRIToTable transform')
        else:
          logging.debug('Creation of MRIToTable transform')

    self.ImageToMRI = slicer.util.getFirstNodeByName('ImageToMRI', className='vtkMRMLLinearTransformNode')
    if not self.ImageToMRI:
      self.ImageToMRIFilePath = os.path.join(self.moduleTransformsPath, 'ImageToMRI.h5')
      [success, self.ImageToMRI] = slicer.util.loadTransform(self.ImageToMRIFilePath, returnNode=True)
      if success == True:
        self.MRIToTable.SetName("ImageToMRI")
        slicer.mrmlScene.AddNode(self.ImageToMRI)
      else:
        logging.debug('Could not load ImageToMRI from file')
        self.ImageToMRI = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'ImageToMRI')
        if not self.ImageToMRI:
          logging.debug('Failed: Creation of ImageToMRI transform')
        else:
          logging.debug('Creation of ImageToMRI transform')

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
          
    #Setup Us Probe Transforms
    self.ImageToProbe = slicer.util.getFirstNodeByName('ImageToProbe', className='vtkMRMLLinearTransformNode')
    if not self.ImageToProbe:
      ImageToProbeFilePath = os.path.join(self.moduleTransformsPath, 'ImageToProbe.h5')
      [success, self.ImageToProbe] = slicer.util.loadTransform(ImageToProbeFilePath, returnNode = True)
      if success == True:
        self.ImageToProbe.SetName("ImageToProbe")
        slicer.mrmlScene.AddNode(self.ImageToProbe)
      else:
        logging.debug('Could not load ImageToProbe from file')
        self.ImageToProbe = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'ImageToProbe')
        if not self.ImageToProbe:
          logging.debug('Failed: Creation of ImageToProbe transform')
        else:
          logging.debug('Creation of ImageToProbe transform')
    
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
      
    self.ProbeToReference = slicer.util.getFirstNodeByName('ProbeToReference', className='vtkMRMLLinearTransformNode')
    if not self.ProbeToReference:
      self.ProbeToReference=slicer.vtkMRMLLinearTransformNode()
      self.ProbeToReference.SetName("ProbeToReference")
      slicer.mrmlScene.AddNode(self.ProbeToReference)



    # Build Transform Tree

    # US Calibration Austria Names
    self.TableToProbe.SetAndObserveTransformNodeID(self.ProbeToUS.GetID())
    self.MRIToTable.SetAndObserveTransformNodeID(self.TableToProbe.GetID())
    self.ImageToMRI.SetAndObserveTransformNodeID(self.MRIToTable.GetID())

    self.StylusToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.StylusTipToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.StylusModel_StylusTip.SetAndObserveTransformNodeID(self.StylusTipToStylus.GetID())
    self.StylusBaseToStylus.SetAndObserveTransformNodeID(self.StylusToReference.GetID())
    self.NeedleToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.NeedleTipToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.NeedleModel_NeedleTip.SetAndObserveTransformNodeID(self.NeedleTipToNeedle.GetID())
    self.NeedleBaseToNeedle.SetAndObserveTransformNodeID(self.NeedleToReference.GetID())
    self.ProbeToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    self.ImageToProbe.SetAndObserveTransformNodeID(self.ProbeToReference.GetID())
    self.CTToReference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())


    # Markups Nodes

    # US Calibration Austria Names
    self.FromProbeToUSFiducialNode = slicer.util.getFirstNodeByName('FromProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode')
    if not self.FromProbeToUSFiducialNode:
      self.FromProbeToUSFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.FromProbeToUSFiducialNode.SetName('FromProbeToUSFiducialNode')
      slicer.mrmlScene.AddNode(self.FromProbeToUSFiducialNode)

    self.ToProbeToUSFiducialNode = slicer.util.getFirstNodeByName('ToProbeToUSFiducialNode', className='vtkMRMLMarkupsFiducialNode')
    if not self.ToProbeToUSFiducialNode:
      self.ToProbeToUSFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.ToProbeToUSFiducialNode.SetName('ToProbeToUSFiducialNode')
      slicer.mrmlScene.AddNode(self.ToProbeToUSFiducialNode)


    self.FromUSToReferenceFiducialNode = slicer.util.getFirstNodeByName('FromUSToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode')
    if not self.FromUSToReferenceFiducialNode:
      self.FromUSToReferenceFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.FromUSToReferenceFiducialNode.SetName('FromUSToReferenceFiducials')
      slicer.mrmlScene.AddNode(self.FromUSToReferenceFiducialNode)
      
    self.ToUSToReferenceFiducialNode = slicer.util.getFirstNodeByName('ToUSToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode')
    if not self.ToUSToReferenceFiducialNode:
      self.ToUSToReferenceFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.ToUSToReferenceFiducialNode.SetName('ToUSToReferenceFiducials')
      slicer.mrmlScene.AddNode(self.ToUSToReferenceFiducialNode)
    
    self.FromCTToReferenceFiducialNode = slicer.util.getFirstNodeByName('FromCTToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode')
    if not self.FromCTToReferenceFiducialNode:
      self.FromCTToReferenceFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.FromCTToReferenceFiducialNode.SetName('FromCTToReferenceFiducials')
      slicer.mrmlScene.AddNode(self.FromCTToReferenceFiducialNode)
      
    self.ToCTToReferenceFiducialNode = slicer.util.getFirstNodeByName('ToCTToReferenceFiducials', className='vtkMRMLMarkupsFiducialNode')
    if not self.ToCTToReferenceFiducialNode:
      self.ToCTToReferenceFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.ToCTToReferenceFiducialNode.SetName('ToCTToReferenceFiducials')
      slicer.mrmlScene.AddNode(self.ToCTToReferenceFiducialNode)


  def cleanup(self):
    pass


  def changeCollapsedView(self, expandedBox):
    logging.debug('changeCollapsedView')
    #TODO fix toggling of collapsible boxes so only one can be active
    
    # print(expandedBox)
    
    # if expandedBox == "ConnectPLUSBox": 
      # self.ui.ConnectPLUSBox.setProperty('collapsed', False)
    # else:
      # self.ui.ConnectPLUSBox.setProperty('collapsed', True)
    
    # if expandedBox == "FineCTRegistrationBox": 
      # self.ui.FineCTRegistrationBox.setProperty('collapsed', False)
    # else:
      # self.ui.FineCTRegistrationBox.setProperty('collapsed', True)
      
    # if expandedBox == "InitialCTRegistrationBox": 
      # self.ui.InitialCTRegistrationBox.setProperty('collapsed', False)
    # else:
      # self.ui.InitialCTRegistrationBox.setProperty('collapsed', True)
      
    # if expandedBox == "NavigationBox": 
      # self.ui.NavigationBox.setProperty('collapsed', False)
    # else:
      # self.ui.NavigationBox.setProperty('collapsed', True)
      
    # if expandedBox == "NeedleCalibrationBox": 
      # self.ui.NeedleCalibrationBox.setProperty('collapsed', False)
    # else:
      # self.ui.NeedleCalibrationBox.setProperty('collapsed', True)
      
    # if expandedBox == "ProbeCalibrationBox": 
      # self.ui.ProbeCalibrationBox.setProperty('collapsed', False)
    # else:
      # self.ui.ProbeCalibrationBox.setProperty('collapsed', True)
      
    # if expandedBox == "SettingsBox": 
      # self.ui.SettingsBox.setProperty('collapsed', False)
    # else:
      # self.ui.SettingsBox.setProperty('collapsed', True)
    
    # if expandedBox == "StylusCalibrationBox": 
      # self.ui.StylusCalibrationBox.setProperty('collapsed', False)
    # else:
      # self.ui.StylusCalibrationBox.setProperty('collapsed', True)


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


  def placeToUSToReferenceFiducial(self):
    logging.debug("placeToUSToReferenceFiducial")
    
    currentNode = self.ui.toProbeToUSFiducialWidget.currentNode()
    
    self.markupsLogic.SetActiveListID(currentNode)
    newFiducial = self.returnTransformedPointAtStylusTip(self.ProbeToReference)
    
    currentNode.AddFiducialFromArray(newFiducial)


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


  def onTestFunction(self):
    
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
  
  def landmarkRegistration(self, fromMarkupsNode, toMarkupsNode, outputTransformNode):
    logging.debug('landmarkRegistration')
    
    fromPoints = vtk.vtkPoints()
    toPoints = vtk.vtkPoints()

    nFromPoints = fromMarkupsNode.GetNumberOfFiducials()
    nToPoints = toMarkupsNode.GetNumberOfFiducials()
    
    if nFromPoints != nToPoints:
      return 'Number of points in markups nodes are not equal'
      
    if nFromPoints < 3:
      return 'Insufficient number of points in markups nodes'

    for i in range( nFromPoints ):
      p = [0, 0, 0]
      fromMarkupsNode.GetNthFiducialPosition(i, p)
      fromPoints.InsertNextPoint( p )
      toMarkupsNode.GetNthFiducialPosition(i, p)
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
      return 'Unstable registration. Check input for collinear points'
      
    outputTransformNode.SetMatrixTransformToParent(resultsMatrix)
    
    return self.calculateRMSE(nFromPoints, fromPoints, toPoints, resultsMatrix)
    
    
  def calculateRMSE(self, nPoints, fromPoints, toPoints, transformMatrix):
    logging.debug('calculateRMSE')
    sumSquareError = 0
    #T = transformMatrix.Get
    
    for i in range( nPoints ):
      pFrom = fromPoints.GetPoint(i)
      pTo = toPoints.GetPoint(i)
      
      #transform from point
      pFrom = [pFrom[0], pFrom[1], pFrom[2], 1]
      transformMatrix.MultiplyPoint(pFrom, pFrom)
      
      dist = (pTo[0] - pFrom[0])**2+(pTo[1] - pFrom[1])**2+(pTo[2] - pFrom[2])**2
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
