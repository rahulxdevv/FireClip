import { AuthForm, AuthLayout, AuthSwitch } from "@/components/auth-form";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your workspace and pick up where the footage left off."
      footer={<AuthSwitch mode="login" />}
    >
      <AuthForm mode="login" />
    </AuthLayout>
  );
}
