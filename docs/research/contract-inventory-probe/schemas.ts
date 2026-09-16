import { z } from 'zod';
export const Count = z.string().min(1).transform(value => value.length);
export type CountInput = z.input<typeof Count>;
export type CountOutput = z.output<typeof Count>;
