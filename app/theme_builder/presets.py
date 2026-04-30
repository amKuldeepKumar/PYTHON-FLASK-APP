from __future__ import annotations

BUILTIN_PRESETS = [
    {
        "key": "ai-dark",
        "name": "AI Dark",
        "values": {
            "primary": "#0d6efd", "bg": "#06111f", "surface": "#0b1a2c", "surface_2": "#0f2238",
            "text": "rgba(255,255,255,.92)", "muted": "rgba(255,255,255,.62)", "border": "rgba(255,255,255,.08)",
            "radius": "16px", "shadow": "0 12px 30px rgba(0,0,0,.45)", "input_bg": "rgba(255,255,255,.04)",
            "input_border": "rgba(255,255,255,.10)", "background_mode": "solid", "glass_level": "low",
            "hover_style": "subtle", "icon_style": "bootstrap", "button_shape": "rounded",
            "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Bahnschrift, Segoe UI, Arial, Helvetica, sans-serif",
            "accent_font_family": "Consolas, Cascadia Mono, SFMono-Regular, Menlo, monospace"
        },
    },
    {
        "key": "neon-purple",
        "name": "Neon Purple",
        "values": {
            "primary": "#b026ff", "bg": "#090414", "surface": "#120923", "surface_2": "#1a0f30",
            "text": "rgba(255,255,255,.95)", "muted": "rgba(255,255,255,.70)", "border": "rgba(176,38,255,.32)",
            "radius": "18px", "shadow": "0 18px 42px rgba(54,0,102,.45)", "input_bg": "rgba(255,255,255,.05)",
            "input_border": "rgba(176,38,255,.30)", "background_mode": "gradient", "gradient_start": "#090414",
            "gradient_end": "#1a0f30", "glass_level": "medium", "hover_style": "glow",
            "icon_style": "futuristic-outline", "button_shape": "glass",
            "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Bahnschrift, Trebuchet MS, Segoe UI, sans-serif",
            "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
    {
        "key": "cyber-blue",
        "name": "Cyber Blue",
        "values": {
            "primary": "#00b7ff", "bg": "#04111b", "surface": "#082033", "surface_2": "#0c2a44",
            "text": "rgba(255,255,255,.94)", "muted": "rgba(255,255,255,.68)", "border": "rgba(0,183,255,.24)",
            "radius": "16px", "shadow": "0 16px 38px rgba(0,35,60,.45)", "input_bg": "rgba(255,255,255,.04)",
            "input_border": "rgba(0,183,255,.22)", "background_mode": "gradient", "gradient_start": "#04111b",
            "gradient_end": "#0c2a44", "glass_level": "low", "hover_style": "lift",
            "icon_style": "futuristic-filled", "button_shape": "rounded",
            "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Bahnschrift, Segoe UI, Arial, sans-serif",
            "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
    {
        "key": "aurora-glass",
        "name": "Aurora Glass",
        "values": {
            "primary": "#3ee8ff", "bg": "#071019", "surface": "rgba(14,26,40,.75)", "surface_2": "rgba(18,34,52,.78)",
            "text": "rgba(255,255,255,.94)", "muted": "rgba(255,255,255,.72)", "border": "rgba(255,255,255,.12)",
            "radius": "20px", "shadow": "0 20px 50px rgba(0,0,0,.35)", "input_bg": "rgba(255,255,255,.06)",
            "input_border": "rgba(255,255,255,.16)", "background_mode": "fluid", "fluid_enabled": True,
            "glass_level": "high", "hover_style": "glow", "icon_style": "neon", "button_shape": "glass",
            "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Bahnschrift, Segoe UI, Arial, sans-serif",
            "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
    {
        "key": "light-futuristic",
        "name": "Light Futuristic",
        "values": {
            "primary": "#2563eb", "bg": "#eef6ff", "surface": "#ffffff", "surface_2": "#dfeefe",
            "text": "#14213d", "muted": "rgba(20,33,61,.68)", "border": "rgba(37,99,235,.16)",
            "radius": "18px", "shadow": "0 18px 50px rgba(37,99,235,.12)", "input_bg": "rgba(255,255,255,.96)",
            "input_border": "rgba(37,99,235,.18)", "background_mode": "gradient", "gradient_start": "#f7fbff",
            "gradient_end": "#dcecff", "glass_level": "low", "hover_style": "lift", "icon_style": "bootstrap",
            "button_shape": "rounded", "heading_text": "#0f172a", "badge_bg": "rgba(37,99,235,.08)",
            "badge_text": "#0f172a", "badge_border": "rgba(37,99,235,.14)",
            "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Bahnschrift, Segoe UI, Arial, sans-serif", "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
    {
        "key": "robotic-light",
        "name": "Robotic Light",
        "values": {
            "primary": "#00a7a0", "bg": "#edfdfb", "surface": "#ffffff", "surface_2": "#d8fbf6",
            "text": "#0b1f1d", "muted": "rgba(11,31,29,.64)", "border": "rgba(0,167,160,.18)",
            "radius": "16px", "shadow": "0 18px 44px rgba(0,167,160,.12)", "input_bg": "#ffffff",
            "input_border": "rgba(0,167,160,.22)", "background_mode": "gradient", "gradient_start": "#f7fffe",
            "gradient_end": "#d7fff7", "glass_level": "low", "hover_style": "glow", "icon_style": "futuristic-filled",
            "button_shape": "sharp", "heading_text": "#07201d",
            "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Bahnschrift, Segoe UI, Arial, sans-serif", "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
    {
        "key": "illusion-spectrum",
        "name": "Illusion Spectrum",
        "values": {
            "primary": "#ff4fd8", "bg": "#fff6fd", "surface": "rgba(255,255,255,.82)", "surface_2": "rgba(255,243,252,.92)",
            "text": "#351248", "muted": "rgba(53,18,72,.68)", "border": "rgba(255,79,216,.18)",
            "radius": "22px", "shadow": "0 22px 56px rgba(255,79,216,.16)", "input_bg": "rgba(255,255,255,.88)",
            "input_border": "rgba(255,79,216,.18)", "background_mode": "fluid", "fluid_enabled": True,
            "fluid_color_1": "#ff9bf2", "fluid_color_2": "#8cc8ff", "fluid_color_3": "#ffe17c",
            "glass_level": "medium", "hover_style": "slide", "icon_style": "neon", "button_shape": "glass",
            "heading_text": "#2a093f", "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Trebuchet MS, Segoe UI, Arial, sans-serif", "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
    {
        "key": "colorful-prism",
        "name": "Colorful Prism",
        "values": {
            "primary": "#ff6b00", "bg": "#fffaf2", "surface": "#ffffff", "surface_2": "#fff0db",
            "text": "#32210e", "muted": "rgba(50,33,14,.64)", "border": "rgba(255,107,0,.18)",
            "radius": "20px", "shadow": "0 20px 50px rgba(255,107,0,.14)", "input_bg": "#ffffff",
            "input_border": "rgba(255,107,0,.18)", "background_mode": "fluid", "fluid_enabled": True,
            "fluid_color_1": "#ff9f43", "fluid_color_2": "#7c4dff", "fluid_color_3": "#00c2ff",
            "glass_level": "low", "hover_style": "lift", "icon_style": "bootstrap", "button_shape": "pill",
            "heading_text": "#221304", "badge_bg": "rgba(255,107,0,.10)", "badge_text": "#3f2404",
            "badge_border": "rgba(255,107,0,.16)", "font_family": "Segoe UI, Arial, Helvetica, sans-serif",
            "heading_font_family": "Trebuchet MS, Segoe UI, Arial, sans-serif", "accent_font_family": "Consolas, Cascadia Mono, monospace"
        },
    },
]


def get_preset_by_key(key: str) -> dict | None:
    key = (key or "").strip().lower()
    for preset in BUILTIN_PRESETS:
        if preset["key"] == key:
            return preset
    return None
