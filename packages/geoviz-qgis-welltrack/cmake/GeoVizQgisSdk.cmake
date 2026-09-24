# GeoVizQgisSdk.cmake — standalone admission of the vendored QGIS SDK for the
# geoviz-qgis-welltrack package.
#
# Mirrors paleo-workbench's cmake/PwbQgisSdk.cmake contract (same environment
# variable names, same read-only consumption of the vendored install tree) so
# the kernel and the host resolve the *same* SDK, but this file is
# self-contained: geo-viz-engine must be buildable without paleo-workbench's
# CMake tree.
#
# Consumption modes:
#   1. A parent project already imported the SDK and exposes the interface
#      target `PwbQgis::Sdk` (paleo-workbench): reused as-is, nothing imported.
#   2. Standalone: SDK located via cache vars or environment variables
#        PALEO_QGIS_SOURCE_DIR  - vendored QGIS source snapshot (headers)
#        PALEO_QGIS_SDK_DIR     - vendored install tree (lib/)
#        PALEO_QGIS_BUILD_DIR   - vendor build dir (generated headers)
#        PWB_QGIS_DEPS_PREFIX   - dependency prefix (optional include closure)
#      and imported as interface targets GeoVizQgis::{Core,Gui,Analysis,Sdk}.
#
# License note: this links GPL-2.0-or-later QGIS libraries; no QGIS source is
# vendored into this repository (docs/development/qgis-welltrack-kernel/
# 04-license-provenance.md).

function(geoviz_qgis_sdk_path var default)
  if(NOT DEFINED ${var})
    if(DEFINED ENV{${var}})
      set(${var} "$ENV{${var}}" CACHE PATH "${var} (from environment)")
    else()
      set(${var} "${default}" CACHE PATH "${var}")
    endif()
  endif()
endfunction()

if(TARGET PwbQgis::Sdk)
  # Host already imported the SDK (paleo-workbench build). The host's own
  # pwb_sdk_path() has defined the PALEO_* cache vars, so runtime locations
  # still resolve; the host's Sdk interface closure covers core+gui headers
  # and symbols, satisfying both the core and gui libraries here.
  set(GEOVIZ_QGIS_SDK_INTERFACE "PwbQgis::Sdk" CACHE INTERNAL "QGIS SDK interface target")
  set(GEOVIZ_QGIS_SDK_CORE_INTERFACE "PwbQgis::Sdk" CACHE INTERNAL "QGIS core SDK interface target")
  geoviz_qgis_sdk_path(PALEO_QGIS_SDK_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../native/qgis_render_bridge/build/qgis-vendor/output")
  set(GEOVIZ_QGIS_RUNTIME "${PALEO_QGIS_SDK_DIR}/lib" CACHE INTERNAL "QGIS runtime SO dir")
  return()
endif()

geoviz_qgis_sdk_path(PALEO_QGIS_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/qgis")
geoviz_qgis_sdk_path(PALEO_QGIS_SDK_DIR
  "${CMAKE_CURRENT_SOURCE_DIR}/../native/qgis_render_bridge/build/qgis-vendor/output")
geoviz_qgis_sdk_path(PALEO_QGIS_BUILD_DIR
  "${CMAKE_CURRENT_SOURCE_DIR}/../native/qgis_render_bridge/build/qgis-vendor")
geoviz_qgis_sdk_path(PWB_QGIS_DEPS_PREFIX "/home/kevin/pwb-sdks/root/usr")

if(NOT EXISTS "${PALEO_QGIS_SOURCE_DIR}/src/core/qgsapplication.h")
  message(FATAL_ERROR
    "geoviz-qgis-welltrack: QGIS source snapshot missing at ${PALEO_QGIS_SOURCE_DIR}. "
    "Set PALEO_QGIS_SOURCE_DIR (cache or environment) to the vendored QGIS 4.2 "
    "source tree used by the host.")
endif()

foreach(_lib qgis_core qgis_gui)
  if(WIN32)
    if(NOT EXISTS "${PALEO_QGIS_SDK_DIR}/lib/${_lib}.lib")
      message(FATAL_ERROR "geoviz-qgis-welltrack: ${_lib}.lib missing under ${PALEO_QGIS_SDK_DIR}/lib")
    endif()
  else()
    if(NOT EXISTS "${PALEO_QGIS_SDK_DIR}/lib/lib${_lib}.so")
      message(FATAL_ERROR "geoviz-qgis-welltrack: lib${_lib}.so missing under ${PALEO_QGIS_SDK_DIR}/lib")
    endif()
  endif()
endforeach()

find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Widgets Xml Svg PrintSupport)

foreach(_comp Core Gui)
  string(TOLOWER "${_comp}" _lower)
  add_library(GeoVizQgis::${_comp} SHARED IMPORTED GLOBAL)
  if(WIN32)
    set_target_properties(GeoVizQgis::${_comp} PROPERTIES
      IMPORTED_IMPLIB   "${PALEO_QGIS_SDK_DIR}/lib/qgis_${_lower}.lib"
      IMPORTED_LOCATION "${PALEO_QGIS_SDK_DIR}/bin/qgis_${_lower}.dll")
  else()
    set_target_properties(GeoVizQgis::${_comp} PROPERTIES
      IMPORTED_LOCATION "${PALEO_QGIS_SDK_DIR}/lib/libqgis_${_lower}.so")
  endif()
endforeach()

# QGIS public headers include across their component subdirectories without
# qualifiers; mirror the upstream target search path (same closure as
# PwbQgisSdk.cmake: source component dirs + recursive header dirs + vendor
# build generated headers + external deps headers).
file(GLOB_RECURSE _geoviz_qwt_core_headers CONFIGURE_DEPENDS
  "${PALEO_QGIS_SOURCE_DIR}/src/core/*.h" "${PALEO_QGIS_SOURCE_DIR}/src/core/*.hpp")
file(GLOB_RECURSE _geoviz_qwt_gui_headers CONFIGURE_DEPENDS
  "${PALEO_QGIS_SOURCE_DIR}/src/gui/*.h" "${PALEO_QGIS_SOURCE_DIR}/src/gui/*.hpp")
function(_geoviz_qwt_header_dirs out_var)
  set(_dirs)
  foreach(_header IN LISTS ARGN)
    get_filename_component(_dir "${_header}" DIRECTORY)
    list(APPEND _dirs "${_dir}")
  endforeach()
  list(REMOVE_DUPLICATES _dirs)
  set(${out_var} "${_dirs}" PARENT_SCOPE)
endfunction()
_geoviz_qwt_header_dirs(_geoviz_qwt_core_dirs ${_geoviz_qwt_core_headers})
_geoviz_qwt_header_dirs(_geoviz_qwt_gui_dirs ${_geoviz_qwt_gui_headers})

file(GLOB _geoviz_qwt_qwt_dir "${PALEO_QGIS_SOURCE_DIR}/external/qwt-*")

# Core-only closure: QGIS core headers + core lib + Qt Core/Gui. Consumers
# that must not see QGIS gui / QtWidgets (geoviz_qgis_welltrack_core) link
# this; the full Sdk below adds gui + widgets.
add_library(GeoVizQgis::SdkCore INTERFACE IMPORTED GLOBAL)
target_include_directories(GeoVizQgis::SdkCore INTERFACE
  "${PALEO_QGIS_SOURCE_DIR}/src/core"
  "${PALEO_QGIS_SOURCE_DIR}/src/analysis"
  ${_geoviz_qwt_core_dirs}
  "${PALEO_QGIS_SOURCE_DIR}/external/nlohmann"
  "${PALEO_QGIS_SOURCE_DIR}/external/spatialindex/include"
  "${PALEO_QGIS_BUILD_DIR}"
  "${PALEO_QGIS_BUILD_DIR}/src/core"
  "${PWB_QGIS_DEPS_PREFIX}/include")
target_link_libraries(GeoVizQgis::SdkCore INTERFACE GeoVizQgis::Core Qt6::Core Qt6::Gui)
set(GEOVIZ_QGIS_SDK_CORE_INTERFACE "GeoVizQgis::SdkCore" CACHE INTERNAL "QGIS core-only SDK interface target")

add_library(GeoVizQgis::Sdk INTERFACE IMPORTED GLOBAL)
target_include_directories(GeoVizQgis::Sdk INTERFACE
  "${PALEO_QGIS_SOURCE_DIR}/src/core"
  "${PALEO_QGIS_SOURCE_DIR}/src/gui"
  "${PALEO_QGIS_SOURCE_DIR}/src/analysis"
  ${_geoviz_qwt_core_dirs}
  ${_geoviz_qwt_gui_dirs}
  "${PALEO_QGIS_SOURCE_DIR}/external/nlohmann"
  "${PALEO_QGIS_SOURCE_DIR}/external/spatialindex/include"
  "${PALEO_QGIS_BUILD_DIR}"
  "${PALEO_QGIS_BUILD_DIR}/src/core"
  "${PALEO_QGIS_BUILD_DIR}/src/gui"
  "${PWB_QGIS_DEPS_PREFIX}/include")
if(_geoviz_qwt_qwt_dir)
  list(GET _geoviz_qwt_qwt_dir 0 _geoviz_qwt_qwt_first)
  target_include_directories(GeoVizQgis::Sdk INTERFACE "${_geoviz_qwt_qwt_first}")
endif()
target_link_libraries(GeoVizQgis::Sdk INTERFACE
  GeoVizQgis::Core GeoVizQgis::Gui
  Qt6::Core Qt6::Gui Qt6::Widgets Qt6::Xml Qt6::Svg Qt6::PrintSupport)

set(GEOVIZ_QGIS_SDK_INTERFACE "GeoVizQgis::Sdk" CACHE INTERNAL "QGIS SDK interface target")
set(GEOVIZ_QGIS_RUNTIME "${PALEO_QGIS_SDK_DIR}/lib" CACHE INTERNAL "QGIS runtime SO dir")
