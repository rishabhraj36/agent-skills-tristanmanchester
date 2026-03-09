import { Stack } from "expo-router";
import { MonetizationProviders } from "./monetization.shared";

export default function RootLayout() {
  return (
    <MonetizationProviders>
      <Stack screenOptions={{ headerShown: false }} />
    </MonetizationProviders>
  );
}
