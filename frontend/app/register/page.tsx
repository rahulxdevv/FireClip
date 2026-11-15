import { AuthForm, AuthLayout, AuthSwitch } from "@/components/auth-form";

export const metadata = { title: "Create your workspace" };

export default function RegisterPage() {
  return (
    <AuthLayout
      title="Create your workspace"
      subtitle="Bring a video, find the clips, and keep every file on infrastructure you control."
      footer={<AuthSwitch mode="register" />}
    >
      <AuthForm mode="register" />
    </AuthLayout>
  );
}
