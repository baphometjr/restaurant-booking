import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("รูปแบบอีเมลไม่ถูกต้อง"),
  password: z.string().min(1, "กรุณากรอกรหัสผ่าน"),
});

export const registerSchema = z.object({
  email: z.string().email("รูปแบบอีเมลไม่ถูกต้อง"),
  password: z
    .string()
    .min(8, "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร")
    .regex(/[A-Z]/, "ต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว")
    .regex(/[0-9]/, "ต้องมีตัวเลขอย่างน้อย 1 ตัว")
    .regex(/[^A-Za-z0-9]/, "ต้องมีอักขระพิเศษอย่างน้อย 1 ตัว"),
  full_name: z.string().min(2, "ชื่อต้องมีอย่างน้อย 2 ตัวอักษร"),
  phone: z
    .string()
    .regex(/^0\d{9}$/, "รูปแบบเบอร์โทรไม่ถูกต้อง")
    .optional()
    .or(z.literal("")),
});

export type LoginFormData = z.infer<typeof loginSchema>;
export type RegisterFormData = z.infer<typeof registerSchema>;
