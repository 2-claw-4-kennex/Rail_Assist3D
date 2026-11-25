
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/Rail_Assist3D/",
  plugins: [react()],
  server: {
    port: 3000,
  },
});
