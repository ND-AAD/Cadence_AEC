/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // — Surface hierarchy (paper grades) —
        sheet: "#FAF9F6",
        vellum: "#F0EFEC",
        board: "#E7E5E2",

        // — Text hierarchy (ink on paper) —
        ink: "#1C1B18",
        graphite: "#57554F",
        trace: "#9D9B95",

        // — Borders (architectural rules) —
        rule: {
          DEFAULT: "#DFDDD9",
          emphasis: "#CECCC7",
        },

        // — Conflicts (redline — Wada vermillion C9 M90 Y100 K0) —
        redline: {
          DEFAULT: "#E81A00",
          muted: "#EE6A53",
          wash: "#FFF0EB",
          ink: "#A61400",
        },

        // — Changes (pencil — Wada amber C2 M42 Y74 K0) —
        pencil: {
          DEFAULT: "#FA9442",
          muted: "#FBB978",
          wash: "#FFF5EA",
          ink: "#B06218",
        },

        // — Resolved (approval stamp) —
        stamp: {
          DEFAULT: "#3D7A4F",
          wash: "#F0F7F2",
          ink: "#2D5E3B",
        },

        // — Hold (filed away) —
        filed: "#7D7A75",

        // — Comparison mode (overlay — Klein blue departure) —
        overlay: {
          DEFAULT: "#002FA7",
          wash: "#EFF2FB",
          border: "#6A7EB5",
        },
      },

      fontFamily: {
        sans: [
          '"Geist Sans"',
          '"Geist"',
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: [
          '"Geist Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },

      fontSize: {
        xs: ["0.6875rem", { lineHeight: "1rem" }], // 11px
        sm: ["0.75rem", { lineHeight: "1.125rem" }], // 12px
        base: ["0.8125rem", { lineHeight: "1.25rem" }], // 13px
        md: ["0.875rem", { lineHeight: "1.375rem" }], // 14px
        lg: ["1rem", { lineHeight: "1.5rem" }], // 16px
        xl: ["1.125rem", { lineHeight: "1.625rem" }], // 18px
        "2xl": ["1.375rem", { lineHeight: "1.75rem" }], // 22px
      },

      borderRadius: {
        sm: "2px",
        DEFAULT: "3px",
        md: "4px",
        lg: "6px",
      },

      boxShadow: {
        float:
          "0 2px 8px rgba(28, 27, 24, 0.08), 0 1px 2px rgba(28, 27, 24, 0.04)",
      },

      keyframes: {
        "slide-in-from-right": {
          from: { transform: "translateX(40px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "slide-in-from-left": {
          from: { transform: "translateX(-40px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },

      animation: {
        "slide-in-right": "slide-in-from-right 200ms ease-out",
        "slide-in-left": "slide-in-from-left 200ms ease-out",
        "fade-in": "fade-in 150ms ease-out",
      },
    },
  },
  plugins: [],
};
