// Static hosts serve 404.html for unknown paths; make it the app so deep links work.
import { copyFileSync } from "node:fs";
copyFileSync("dist/index.html", "dist/404.html");
