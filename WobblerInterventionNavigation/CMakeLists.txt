cmake_minimum_required(VERSION 3.5)

project(Wobbler Intervention Navigation)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://slicer.org/slicerWiki/index.php/Documentation/Nightly/Extensions/WobblerInterventionNavigation")
set(EXTENSION_CATEGORY "Ultrasound Navigation")
set(EXTENSION_CONTRIBUTORS "Abigael Schonewille (Perk Lab)")
set(EXTENSION_DESCRIPTION "An extension designed to provide the framework to complete 3D ultrasound guided percutaneous interventions.")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/WobblerInterventionNavigation.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/WobblerInterventionNavigation/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(LiverBiopsy)
add_subdirectory(LiverBiopsy)
add_subdirectory(LiverBiopsy_NRTUS)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
