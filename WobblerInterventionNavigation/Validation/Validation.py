import os, math
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# Validation
#

class Validation(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Validation"
    self.parent.categories = ["US guided intervention"]
    self.parent.dependencies = []
    self.parent.contributors = ["Abigael Schonewille (Perk Lab)"]
    self.parent.helpText = """
This is a module that contains functions for validating and testing the liver biopsy module.
"""
    self.parent.acknowledgementText = """"""

#
# ValidationWidget
#

class ValidationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/Validation.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    self.logic = ValidationLogic()

    # Connections
    self.ui.USValidationButton.connect('clicked(bool)', self.onUSValidationButton)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def onUSValidationButton(self):
    """
    Run processing when user clicks "USValidationButton" button.
    """
    try:
      USTestPoint1 = slicer.util.getFirstNodeByName('TestPoint-US1', className='vtkMRMLMarkupsFiducialNode')
      USTestPoint2 = slicer.util.getFirstNodeByName('TestPoint-US2', className='vtkMRMLMarkupsFiducialNode')
      USTestPoint3 = slicer.util.getFirstNodeByName('TestPoint-US3', className='vtkMRMLMarkupsFiducialNode')
      USTestPoint4 = slicer.util.getFirstNodeByName('TestPoint-US4', className='vtkMRMLMarkupsFiducialNode')

      calibrationMessage, result = self.logic.MeanDistanceFourPoints(USTestPoint1, USTestPoint2, USTestPoint3, USTestPoint4)

      self.ui.USValidationResult.setText(calibrationMessage.format(result))
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: " +str(e))
      import traceback
      traceback.print_exc()


#
# ValidationLogic
#

class ValidationLogic(ScriptedLoadableModuleLogic):

  def MeanDistanceFourPoints(self, TestPoint1, TestPoint2, TestPoint3, TestPoint4):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param TestPoint1: markups node containing one point transformed by the calibrated Probe to US transforms
    :param TestPoint2: markups node containing one point transformed by the calibrated Probe to US transforms
    :param TestPoint3: markups node containing one point transformed by the calibrated Probe to US transforms
    :param TestPoint4: markups node containing one point transformed by the calibrated Probe to US transforms
    """

    if not TestPoint1 or not TestPoint2 or not TestPoint3 or not TestPoint4:
      raise ValueError("Input paramaters are invalid")

    logging.info('Processing started')

    point1 = vtk.vtkPoints()
    point2 = vtk.vtkPoints()
    point3 = vtk.vtkPoints()
    point4 = vtk.vtkPoints()

    p = [0, 0, 0]
    TestPoint1.GetNthControlPointPositionWorld(0, p)
    point1.InsertNextPoint(p)
    TestPoint2.GetNthControlPointPositionWorld(0, p)
    point2.InsertNextPoint(p)
    TestPoint3.GetNthControlPointPositionWorld(0, p)
    point3.InsertNextPoint(p)
    TestPoint4.GetNthControlPointPositionWorld(0, p)
    point4.InsertNextPoint(p)

    p1 = point1.GetPoint(0)
    p2 = point2.GetPoint(0)
    p3 = point3.GetPoint(0)
    p4 = point4.GetPoint(0)

    centroid = [0, 0, 0]
    centroid[0] = (p1[0] + p2[0] + p3[0] + p4[0]) / 4
    centroid[1] = (p1[1] + p2[1] + p3[1] + p4[1]) / 4
    centroid[2] = (p1[2] + p2[2] + p3[2] + p4[2]) / 4

    print(centroid)

    dist1 = math.sqrt((centroid[0] - p1[0]) ** 2 + (centroid[1] - p1[1]) ** 2 + (centroid[2] - p1[2]) ** 2)
    dist2 = math.sqrt((centroid[0] - p2[0]) ** 2 + (centroid[1] - p2[1]) ** 2 + (centroid[2] - p2[2]) ** 2)
    dist3 = math.sqrt((centroid[0] - p3[0]) ** 2 + (centroid[1] - p3[1]) ** 2 + (centroid[2] - p3[2]) ** 2)
    dist4 = math.sqrt((centroid[0] - p4[0]) ** 2 + (centroid[1] - p4[1]) ** 2 + (centroid[2] - p4[2]) ** 2)

    print(dist1)
    print(dist2)
    print(dist3)
    print(dist4)

    dist = (dist1 + dist2 + dist3 + dist4) / 4
    print(dist)

    logging.info('Processing completed')
    return "Success. Average Distance = {0:.2f} mm", dist

#
# ValidationTest
#

class ValidationTest(ScriptedLoadableModuleTest):
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
    self.test_Validation1()

  def test_Validation1(self):
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

