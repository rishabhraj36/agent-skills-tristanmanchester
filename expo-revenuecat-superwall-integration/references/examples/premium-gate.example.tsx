import { Button, Text, View } from "react-native";
import { usePlacement, useUser } from "expo-superwall";

function hasEntitlement(
  subscriptionStatus: ReturnType<typeof useUser>["subscriptionStatus"],
  entitlementId: string,
) {
  return (
    subscriptionStatus?.entitlements?.some(
      (entitlement) => entitlement.id === entitlementId,
    ) ?? false
  );
}

export function ExportPdfUpsell() {
  const { registerPlacement, state } = usePlacement({
    onPresent: (info) => console.log("Paywall presented", info),
    onDismiss: (info, result) => console.log("Paywall dismissed", { info, result }),
    onError: (error) => console.warn("Paywall placement error", error),
  });

  const { subscriptionStatus } = useUser();
  const isPro = hasEntitlement(subscriptionStatus, "pro");

  return (
    <View style={{ gap: 12 }}>
      <Text style={{ lineHeight: 22 }}>
        Prefer registering the placement and letting Superwall's dashboard logic
        decide whether the user should actually see a paywall.
      </Text>

      <Button
        title={isPro ? "Export PDF" : "Unlock PDF export"}
        onPress={() => {
          void registerPlacement({
            placement: "export_pdf",
            params: {
              source: "editor_toolbar",
              entitlementHint: isPro ? "already_pro" : "not_pro",
            },
          });
        }}
      />

      {state ? <Text selectable>{JSON.stringify(state, null, 2)}</Text> : null}
    </View>
  );
}
