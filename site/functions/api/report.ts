// POST /api/report: file a report from the site's form as a GitHub issue (see src/report/).

import { fileReport, type Env } from "../../src/report/file.ts";

export const onRequestPost = ({ request, env }: { request: Request; env: Env }): Promise<Response> =>
  fileReport(request, env);
