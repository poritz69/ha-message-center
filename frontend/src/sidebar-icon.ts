// Loaded by Home Assistant on every page (frontend extra module). It registers
// the icon set "message-center" so that the sidebar entry can show the logo:
// Home Assistant's ha-icon asks window.customIcons[prefix].getIcon(name).
import { LOGO_PATH, LOGO_VIEWBOX } from "./logo-path";

interface CustomIcons {
  [prefix: string]: { getIcon: (name: string) => Promise<{ path: string; viewBox?: string }> };
}

const host = window as unknown as { customIcons?: CustomIcons };
host.customIcons = host.customIcons ?? {};
host.customIcons["message-center"] = {
  getIcon: async () => ({ path: LOGO_PATH, viewBox: LOGO_VIEWBOX }),
};
