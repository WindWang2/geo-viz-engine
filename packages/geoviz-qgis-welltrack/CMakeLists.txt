# geoviz-qgis-welltrack — QGIS-native well-track plotting kernel
#
# SPDX-License-Identifier: MIT
#
# Two targets:
#   GeoViz::QgisWellTrackCore — data/LOD/layout/renderer/hit-testing (Qt Gui + QGIS core)
#   GeoViz::QgisWellTrack     — WellTrackCanvas + tools + synchronizer (Qt Widgets + QGIS gui)
#
# Consumption: add_subdirectory(packages/geoviz-qgis-welltrack) then
#   target_link_libraries(my_host PRIVATE GeoViz::QgisWellTrack)
#
# Cache options:
#   GEOVIZ_QWT_BUILD_TESTS / GEOVIZ_QWT_BUILD_EXAMPLES (default ON for standalone, OFF when added)

cmake_minimum_required(VERSION 3.24)

project(geoviz-qgis-welltrack LANGUAGES CXX VERSION 0.1.0)

option(GEOVIZ_QWT_BUILD_TESTS "Build geoviz-qgis-welltrack tests" OFF)
option(GEOVIZ_QWT_BUILD_EXAMPLES "Build geoviz-qgis-welltrack examples" OFF)
if(CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
  set(GEOVIZ_QWT_BUILD_TESTS ON)
  set(GEOVIZ_QWT_BUILD_EXAMPLES ON)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(GeoVizQgisSdk)

# --- core library -----------------------------------------------------------
add_library(geoviz_qgis_welltrack_core
  src/axis_spec.cpp
  src/curve_data.cpp
  src/curve_lod.cpp
  src/depth_domain.cpp
  src/hit_testing.cpp
  src/track_layout.cpp
  src/track_model.cpp
  src/welltrack_renderer.cpp)
add_library(GeoViz::QgisWellTrackCore ALIAS geoviz_qgis_welltrack_core)
target_compile_definitions(geoviz_qgis_welltrack_core PRIVATE GEOVIZ_QWT_CORE_LIBRARY)
target_include_directories(geoviz_qgis_welltrack_core
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
target_link_libraries(geoviz_qgis_welltrack_core
  PUBLIC ${GEOVIZ_QGIS_SDK_CORE_INTERFACE} Qt6::Core Qt6::Gui)
set_target_properties(geoviz_qgis_welltrack_core PROPERTIES
  OUTPUT_NAME geoviz_qgis_welltrack_core
  POSITION_INDEPENDENT_CODE ON
  AUTOMOC ON)

# NaN-aware math: the LOD/gap logic relies on std::isfinite checks; never let
# -ffast-math style flags strip them (lesson from native/map_edit_core).
target_compile_options(geoviz_qgis_welltrack_core PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-fno-fast-math;-fno-finite-math-only>)

# --- gui library -------------------------------------------------------------
add_library(geoviz_qgis_welltrack_gui
  src/gui/depth_synchronizer.cpp
  src/gui/well_track_canvas.cpp
  src/gui/well_track_scene_item.cpp
  src/gui/well_track_tools.cpp)
add_library(GeoViz::QgisWellTrack ALIAS geoviz_qgis_welltrack_gui)
target_compile_definitions(geoviz_qgis_welltrack_gui PRIVATE GEOVIZ_QWT_GUI_LIBRARY)
target_include_directories(geoviz_qgis_welltrack_gui
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  PRIVATE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>)
target_link_libraries(geoviz_qgis_welltrack_gui
  PUBLIC GeoViz::QgisWellTrackCore Qt6::Widgets
  PRIVATE ${GEOVIZ_QGIS_SDK_INTERFACE})
set_target_properties(geoviz_qgis_welltrack_gui PROPERTIES
  OUTPUT_NAME geoviz_qgis_welltrack
  POSITION_INDEPENDENT_CODE ON
  AUTOMOC ON)
# gui sources include the private scene item header
target_sources(geoviz_qgis_welltrack_gui PRIVATE
  src/gui/well_track_scene_item.h)

# --- tests -------------------------------------------------------------------
if(GEOVIZ_QWT_BUILD_TESTS)
  enable_testing()

  # Pure logic tests: no QApplication event loop, no QGIS registries.
  set(GEOVIZ_QWT_CORE_TESTS
    test_depth_domain
    test_curve_view
    test_axis_transform
    test_visible_slice
    test_envelope
    test_track_layout
    test_hit_testing)
  foreach(test_name IN LISTS GEOVIZ_QWT_CORE_TESTS)
    add_executable(${test_name} tests/${test_name}.cpp)
    target_link_libraries(${test_name} PRIVATE GeoViz::QgisWellTrackCore Qt6::Test)
    add_test(NAME ${test_name} COMMAND ${test_name})
    set_tests_properties(${test_name} PROPERTIES ENVIRONMENT
      "QT_QPA_PLATFORM=offscreen;LD_LIBRARY_PATH=${GEOVIZ_QGIS_RUNTIME}:$ENV{LD_LIBRARY_PATH}")
  endforeach()

  # Renderer needs QgsApplication registries (symbol layers, text renderer).
  set(GEOVIZ_QWT_APP_TESTS test_renderer)
  foreach(test_name IN LISTS GEOVIZ_QWT_APP_TESTS)
    add_executable(${test_name} tests/${test_name}.cpp tests/qgis_app_fixture.h)
    target_link_libraries(${test_name} PRIVATE GeoViz::QgisWellTrackCore Qt6::Test)
    target_include_directories(${test_name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME ${test_name} COMMAND ${test_name})
    set_tests_properties(${test_name} PROPERTIES ENVIRONMENT
      "QT_QPA_PLATFORM=offscreen;QT_QGIS_PREFIX_DIR=${PALEO_QGIS_SDK_DIR};LD_LIBRARY_PATH=${GEOVIZ_QGIS_RUNTIME}:$ENV{LD_LIBRARY_PATH}")
  endforeach()

  # GUI tests: WellTrackCanvas stack (QgsPlotCanvas/QgsPlotTool).
  set(GEOVIZ_QWT_GUI_TESTS test_canvas_core test_canvas_navigation test_canvas_tools test_synchronizer test_perf)
  foreach(test_name IN LISTS GEOVIZ_QWT_GUI_TESTS)
    add_executable(${test_name} tests/${test_name}.cpp tests/qgis_app_fixture.h)
    target_link_libraries(${test_name} PRIVATE GeoViz::QgisWellTrack Qt6::Test)
    target_include_directories(${test_name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    add_test(NAME ${test_name} COMMAND ${test_name})
    set_tests_properties(${test_name} PROPERTIES ENVIRONMENT
      "QT_QPA_PLATFORM=offscreen;QT_QGIS_PREFIX_DIR=${PALEO_QGIS_SDK_DIR};LD_LIBRARY_PATH=${GEOVIZ_QGIS_RUNTIME}:$ENV{LD_LIBRARY_PATH}")
  endforeach()
endif()

# --- example -----------------------------------------------------------------
if(GEOVIZ_QWT_BUILD_EXAMPLES)
  add_executable(welltrack_demo examples/welltrack_demo/main.cpp)
  target_link_libraries(welltrack_demo PRIVATE GeoViz::QgisWellTrack Qt6::Widgets)
  set_target_properties(welltrack_demo PROPERTIES AUTOMOC ON)
endif()
