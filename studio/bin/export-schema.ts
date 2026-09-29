// 导出两份 props 契约的 JSON Schema，供 Python 侧（jsonschema）校验。
// 运行：pnpm exec tsx bin/export-schema.ts
// 输出：src/schemas/timeline-v2.schema.json + report-data.schema.json（提交进 git）

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {z} from 'zod';
import {TimelineV2Schema} from '../src/schemas/timeline-v2';
import {ReportDataSchema} from '../src/schemas/report-data';

const outDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'schemas');

const write = (name: string, schema: z.core.JSONSchema.BaseSchema): void => {
  const p = path.join(outDir, name);
  fs.writeFileSync(p, JSON.stringify(schema, null, 2) + '\n', 'utf-8');
  console.log(`written: ${p}`);
};

write('timeline-v2.schema.json', z.toJSONSchema(TimelineV2Schema, {io: 'input', unrepresentable: 'throw'}));
write('report-data.schema.json', z.toJSONSchema(ReportDataSchema, {io: 'input', unrepresentable: 'throw'}));
