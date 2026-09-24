cmake_minimum_required(VERSION 3.24)

project(geoviz_well_track_native VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets)

# Prompt A integration (docs 04): two resolution paths for
# GeoViz::QgisWellTrack —
#   1. a future install config (find_package, once A exports one);
#   2. A's documented consumption mode: add_subdirectory on its package
#      source (-DGEOVIZ_QGIS_WELLTRACK_DIR=<A worktree>/packages/geoviz-qgis-welltrack).
# A's GeoVizQgisSdk.cmake reads PALEO_QGIS_SOURCE_DIR / PALEO_QGIS_SDK_DIR /
# PALEO_QGIS_BUILD_DIR / PWB_QGIS_DEPS_PREFIX from the environment.
# Without A the package still builds domain/config/data/view layers and the
# widget reports a "no render kernel" state — there is deliberately NO
# fallback rendering engine in this package.
find_package(GeoVizQgisWellTrack QUIET CONFIG)
set(GEOVIZ_QGIS_WELLTRACK_DIR "" CACHE PATH
    "Prompt A package source (packages/geoviz-qgis-welltrack) for add_subdirectory integration")
if(NOT TARGET GeoViz::QgisWellTrack AND GEOVIZ_QGIS_WELLTRACK_DIR
   AND EXISTS "${GEOVIZ_QGIS_WELLTRACK_DIR}/CMakeLists.txt")
  add_subdirectory("${GEOVIZ_QGIS_WELLTRACK_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/qgis-welltrack-build")
endif()
if(TARGET GeoViz::QgisWellTrack)
  set(GEOVIZ_WELL_TRACK_QWT_DEFAULT ON)
else()
  set(GEOVIZ_WELL_TRACK_QWT_DEFAULT OFF)
endif()
option(GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL
       "Build the QgisSurface adapter against GeoViz::QgisWellTrack (Prompt A)"
       ${GEOVIZ_WELL_TRACK_QWT_DEFAULT})
option(GEOVIZ_WELL_TRACK_BUILD_TESTS "Build tests" ON)
option(GEOVIZ_WELL_TRACK_BUILD_EXAMPLES "Build examples" ON)

add_library(
  geoviz_well_track_native
  # domain
  src/domain/curve.cpp
  src/domain/depth.cpp
  src/domain/defaults.cpp
  src/domain/images.cpp
  src/domain/intervals.cpp
  src/domain/markers.cpp
  src/domain/pattern_catalog.cpp
  src/domain/pattern_catalog_data.cpp
  src/domain/robust_range.cpp
  # data / config
  src/data/snapshot.cpp
  src/config/view_config.cpp
  # view
  src/view/document_builder.cpp
  src/view/overlays.cpp
  src/view/surface_registry.cpp
  src/view/well_track_controller.cpp
  src/view/well_track_factory.cpp
  src/view/well_track_widget.cpp
  # public headers (listed so AUTOMOC processes Q_OBJECT declarations)
  include/geoviz/well_track/view/render_surface.h
  include/geoviz/well_track/view/well_track_controller.h
  include/geoviz/well_track/view/well_track_widget.h)

add_library(GeoViz::WellTrackNative ALIAS geoviz_well_track_native)

target_include_directories(
  geoviz_well_track_native
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<INSTALL_INTERFACE:include> PRIVATE src)

target_link_libraries(geoviz_well_track_native PUBLIC Qt6::Core Qt6::Gui Qt6::Widgets)

if(GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL)
  if(NOT TARGET GeoViz::QgisWellTrack)
    message(FATAL_ERROR "GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL=ON but target "
                        "GeoViz::QgisWellTrack is not available (Prompt A).")
  endif()
  find_package(Qt6 6.6 REQUIRED COMPONENTS Svg)  # pattern brush materialization
  target_sources(geoviz_well_track_native PRIVATE src/view/qgis_surface.cpp)
  target_link_libraries(geoviz_well_track_native PUBLIC GeoViz::QgisWellTrack PRIVATE Qt6::Svg)
  target_compile_definitions(geoviz_well_track_native PUBLIC GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL)
  message(STATUS "geoviz-well-track-native: QgisSurface adapter ENABLED (Prompt A kernel)")
else()
  message(
    STATUS
      "geoviz-well-track-native: QgisSurface adapter DISABLED - integrate the "
      "Prompt A kernel via -DGEOVIZ_QGIS_WELLTRACK_DIR=<A>/packages/geoviz-qgis-welltrack "
      "(or an install prefix once A exports one). No fallback renderer is provided.")
endif()

include(GNUInstallDirs)
install(
  TARGETS geoviz_well_track_native
  EXPORT GeoVizWellTrackNativeTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY include/geoviz DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(DIRECTORY assets/patterns
        DESTINATION ${CMAKE_INSTALL_DATADIR}/geoviz/well-track)

include(CMakePackageConfigHelpers)
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/GeoVizWellTrackNativeConfigVersion.cmake
  VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(EXPORT GeoVizWellTrackNativeTargets
        NAMESPACE GeoViz::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/GeoVizWellTrackNative)
file(
  WRITE ${CMAKE_CURRENT_BINARY_DIR}/GeoVizWellTrackNativeConfig.cmake
  "include(CMakeFindDependencyMacro)\nfind_dependency(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets)\ninclude(\"\${CMAKE_CURRENT_LIST_DIR}/GeoVizWellTrackNativeTargets.cmake\")\n"
)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/GeoVizWellTrackNativeConfig.cmake
              ${CMAKE_CURRENT_BINARY_DIR}/GeoVizWellTrackNativeConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/GeoVizWellTrackNative)

if(GEOVIZ_WELL_TRACK_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()

if(GEOVIZ_WELL_TRACK_BUILD_EXAMPLES)
  add_subdirectory(examples)
endif()
