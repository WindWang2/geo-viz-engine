// Wiggle Trace GPU Instancing Shaders (Vertex & Fragment)

// VERTEX SHADER
#version 330 core
layout(location = 0) in vec2 a_vertex; // x=sample_index, y=vertex_type (0.0 = baseline, 1.0 = amplitude curve)

uniform sampler2D u_seismic_tex;
uniform float u_gain;
uniform float u_clip_limit;
uniform float u_trace_spacing;
uniform mat4 u_mvp;

out float v_amplitude;

void main() {
    int trace_idx = gl_InstanceID;
    int sample_idx = int(a_vertex.x);
    float vertex_type = a_vertex.y; // 0.0 for baseline, 1.0 for offset curve

    ivec2 tex_size = textureSize(u_seismic_tex, 0);
    vec2 tex_coord = vec2((float(sample_idx) + 0.5) / float(tex_size.x),
                          (float(trace_idx) + 0.5) / float(tex_size.y));
    float amp = texture(u_seismic_tex, tex_coord).r;
    v_amplitude = amp;

    float base_x = float(trace_idx) * u_trace_spacing;
    float clamped_amp = clamp(amp * u_gain, -u_clip_limit, u_clip_limit);
    float x = base_x + (vertex_type * clamped_amp);
    float y = float(sample_idx);

    gl_Position = u_mvp * vec4(x, y, 0.0, 1.0);
}

// FRAGMENT SHADER
#version 330 core
in float v_amplitude;
uniform int u_mode; // 0=wiggle, 1=positive_fill, 2=dual_fill, 3=overlaid_vd
uniform vec4 u_line_color;
uniform vec4 u_positive_fill_color;
uniform vec4 u_negative_fill_color;
uniform sampler1D u_lut_tex;
uniform float u_vmin;
uniform float u_vmax;
out vec4 FragColor;

void main() {
    if (u_mode == 3) { // Mode D: Overlaid Wiggle + VD
        float norm_amp = clamp((v_amplitude - u_vmin) / (u_vmax - u_vmin + 1e-6), 0.0, 1.0);
        vec4 vd_color = texture(u_lut_tex, norm_amp);
        FragColor = mix(vd_color, u_line_color, u_line_color.a);
    } else if (u_mode == 1) { // Mode B: Positive Fill
        if (v_amplitude > 0.0) {
            FragColor = u_positive_fill_color;
        } else {
            discard;
        }
    } else if (u_mode == 2) { // Mode C: Dual Fill
        if (v_amplitude > 0.0) {
            FragColor = u_positive_fill_color;
        } else if (v_amplitude < 0.0) {
            FragColor = u_negative_fill_color;
        } else {
            discard;
        }
    } else {
        FragColor = u_line_color;
    }
}
