find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets Test)

function(wt_add_test name src)
  add_executable(${name} ${src})
  target_include_directories(${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
                                              ${CMAKE_CURRENT_SOURCE_DIR}/../src)
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
