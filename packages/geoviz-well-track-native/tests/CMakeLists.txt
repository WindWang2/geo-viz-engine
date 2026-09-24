find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets Test)

function(wt_add_test name src)
  add_executable(${name} ${src})
  # Q_OBJECT test headers must be listed for AUTOMOC.
  if(src MATCHES "view/")
    target_sources(${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/mock_surface.h)
  endif()
  target_include_directories(${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
                                              ${CMAKE_CURRENT_SOURCE_DIR}/../src
                                              ${CMAKE_CURRENT_SOURCE_DIR}/../src/view)
  target_link_libraries(${name} PRIVATE geoviz_well_track_native Qt6::Test)
  add_test(
    NAME ${name}
    COMMAND ${name}
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
  set_tests_properties(${name} PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endfunction()

wt_add_test(wt_domain_tests domain/t_domain.cpp)
wt_add_test(wt_config_tests config/t_config_builder.cpp)
wt_add_test(wt_view_tests view/t_view.cpp)

# With the QGIS kernel adapter enabled, the library links QGIS — tests need
# the SDK runtime (paths come from A's GeoVizQgisSdk.cmake cache vars).
if(TARGET GeoViz::QgisWellTrack AND DEFINED GEOVIZ_QGIS_RUNTIME)
  set_tests_properties(
    wt_domain_tests wt_config_tests wt_view_tests
    PROPERTIES ENVIRONMENT
               "QT_QPA_PLATFORM=offscreen;QT_QGIS_PREFIX_DIR=${PALEO_QGIS_SDK_DIR};LD_LIBRARY_PATH=${GEOVIZ_QGIS_RUNTIME}:$ENV{LD_LIBRARY_PATH}"
  )
endif()
