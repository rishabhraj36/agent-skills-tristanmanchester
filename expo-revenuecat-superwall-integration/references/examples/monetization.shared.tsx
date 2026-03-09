import { ReactNode, useEffect, useMemo } from "react";
import { ActivityIndicator, Platform, Text, View } from "react-native";
import Purchases, {
  LOG_LEVEL,
  PURCHASES_ERROR_CODE,
  type CustomerInfo,
} from "react-native-purchases";
import {
  CustomPurchaseControllerProvider,
  SuperwallLoaded,
  SuperwallLoading,
  SuperwallProvider,
  useSuperwallEvents,
  useUser,
} from "expo-superwall";

const revenueCatApiKeys = {
  ios: process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY ?? "",
  android: process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY ?? "",
} as const;

const superwallApiKeys = {
  ios: process.env.EXPO_PUBLIC_SUPERWALL_IOS_API_KEY ?? "",
  android: process.env.EXPO_PUBLIC_SUPERWALL_ANDROID_API_KEY ?? "",
} as const;

const expectedEntitlementIds = ["pro", "premium"];

let purchasesConfigured = false;

function getPlatformKey(keys: { ios: string; android: string }) {
  return Platform.OS === "ios" ? keys.ios : keys.android;
}

function extractCustomerInfo(result: any): CustomerInfo {
  return result?.customerInfo ?? result;
}

function hasExpectedEntitlement(
  customerInfo: CustomerInfo,
  entitlementIds = expectedEntitlementIds,
) {
  return entitlementIds.some(
    (entitlementId) => customerInfo.entitlements.active[entitlementId],
  );
}

function isCancelledError(error: unknown) {
  const code = (error as any)?.code;
  return code === PURCHASES_ERROR_CODE.PURCHASE_CANCELLED_ERROR;
}

function isPendingError(error: unknown) {
  const code = (error as any)?.code;
  return (
    code === (PURCHASES_ERROR_CODE as any).PAYMENT_PENDING_ERROR ||
    code === "PAYMENT_PENDING_ERROR" ||
    code === "paymentPendingError" ||
    /pending/i.test(String((error as any)?.message ?? ""))
  );
}

async function getStoreProduct(productId: string) {
  const products = await Purchases.getProducts([productId]);
  const product = products[0];

  if (!product) {
    throw new Error(`RevenueCat product not found for ${productId}`);
  }

  return product;
}

function getAndroidOptionId(basePlanId?: string, offerId?: string) {
  return [basePlanId, offerId].filter(Boolean).join(":");
}

function resolveAndroidSubscriptionOption(
  storeProduct: any,
  basePlanId?: string,
  offerId?: string,
) {
  const explicitOptionId = getAndroidOptionId(basePlanId, offerId);
  const subscriptionOptions: any[] = Array.isArray(storeProduct?.subscriptionOptions)
    ? storeProduct.subscriptionOptions
    : [];

  if (explicitOptionId) {
    const matchedOption = subscriptionOptions.find(
      (option) => option?.id === explicitOptionId,
    );

    if (matchedOption) {
      return matchedOption;
    }
  }

  return storeProduct?.defaultOption ?? subscriptionOptions[0] ?? null;
}

/**
 * RevenueCat's exact purchase API for subscription options can vary a little
 * across SDK generations. This helper keeps the example adaptable:
 * - prefer an explicit subscription-option purchase method when present
 * - otherwise try a generic purchase call
 * - fall back to `purchaseStoreProduct` as a last resort
 *
 * Adapt this helper to the exact API surface exposed by the installed
 * `react-native-purchases` version in the user's repository.
 */
async function purchaseAndroidSubscriptionOption(
  storeProduct: any,
  basePlanId?: string,
  offerId?: string,
): Promise<CustomerInfo> {
  const option = resolveAndroidSubscriptionOption(storeProduct, basePlanId, offerId);

  if (!option) {
    throw new Error(
      `Could not resolve a Google Play subscription option for product ${storeProduct?.identifier ?? "unknown"}.`,
    );
  }

  const purchasesModule: any = Purchases as any;

  if (typeof purchasesModule.purchaseSubscriptionOption === "function") {
    const result = await purchasesModule.purchaseSubscriptionOption(option);
    return result?.customerInfo ?? result;
  }

  if (typeof purchasesModule.purchase === "function") {
    const result = await purchasesModule.purchase({
      storeProduct,
      subscriptionOption: option,
    });
    return result?.customerInfo ?? result;
  }

  const result = await purchasesModule.purchaseStoreProduct(storeProduct);
  return extractCustomerInfo(result);
}

function MonetizationBootstrap() {
  useEffect(() => {
    if (purchasesConfigured) {
      return;
    }

    const apiKey = getPlatformKey(revenueCatApiKeys);

    if (!apiKey) {
      console.warn("Missing RevenueCat public API key for this platform.");
      return;
    }

    if (__DEV__) {
      Purchases.setLogLevel(LOG_LEVEL.VERBOSE);
    }

    Purchases.configure({ apiKey });
    purchasesConfigured = true;
  }, []);

  return null;
}

function SubscriptionSync() {
  const { setSubscriptionStatus } = useUser();

  useEffect(() => {
    let mounted = true;

    const applyCustomerInfo = async (customerInfo: CustomerInfo) => {
      if (!mounted) {
        return;
      }

      const entitlementIds = Object.keys(customerInfo.entitlements.active);

      await setSubscriptionStatus({
        status: entitlementIds.length > 0 ? "ACTIVE" : "INACTIVE",
        entitlements: entitlementIds.map((id) => ({
          id,
          type: "SERVICE_LEVEL",
        })),
      });
    };

    const listener = Purchases.addCustomerInfoUpdateListener((customerInfo) => {
      void applyCustomerInfo(customerInfo);
    });

    void Purchases.getCustomerInfo()
      .then((customerInfo) => applyCustomerInfo(customerInfo))
      .catch((error) => {
        console.warn("Initial RevenueCat subscription sync failed:", error);
      });

    return () => {
      mounted = false;
      listener?.remove();
    };
  }, [setSubscriptionStatus]);

  return null;
}

function AnalyticsBridge() {
  useSuperwallEvents({
    onPaywallPresent: (paywallInfo) => {
      console.log("Superwall paywall presented", paywallInfo);
    },
    onPaywallDismiss: (paywallInfo, result) => {
      console.log("Superwall paywall dismissed", { paywallInfo, result });
    },
    onSubscriptionStatusChange: (status) => {
      console.log("Superwall subscription status changed", status);
    },
    onPurchase: (params) => {
      console.log("Superwall purchase started", params);
    },
    onPurchaseRestore: () => {
      console.log("Superwall restore started");
    },
    onPaywallError: (error) => {
      console.warn("Superwall paywall error", error);
    },
  });

  return null;
}

function LoadingState() {
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <ActivityIndicator />
      <Text style={{ marginTop: 12 }}>Loading subscriptions…</Text>
    </View>
  );
}

type MonetizationProvidersProps = {
  children: ReactNode;
};

export function MonetizationProviders({
  children,
}: MonetizationProvidersProps) {
  const controller = useMemo(
    () => ({
      onPurchase: async ({
        productId,
        basePlanId,
        offerId,
      }: {
        productId: string;
        basePlanId?: string;
        offerId?: string;
      }) => {
        try {
          const storeProduct = await getStoreProduct(productId);

          const customerInfo =
            Platform.OS === "android" && (basePlanId || offerId)
              ? await purchaseAndroidSubscriptionOption(
                  storeProduct,
                  basePlanId,
                  offerId,
                )
              : extractCustomerInfo(await Purchases.purchaseStoreProduct(storeProduct));

          if (!hasExpectedEntitlement(customerInfo)) {
            return {
              type: "failed",
              error:
                "Purchase completed, but the expected entitlement is still inactive. Check RevenueCat and Superwall product and entitlement mappings.",
            } as const;
          }

          return { type: "purchased" } as const;
        } catch (error) {
          if (isCancelledError(error)) {
            return { type: "cancelled" } as const;
          }

          if (isPendingError(error)) {
            return { type: "pending" } as const;
          }

          return {
            type: "failed",
            error: (error as any)?.message ?? "Purchase failed",
          } as const;
        }
      },

      onPurchaseRestore: async () => {
        try {
          const customerInfo = extractCustomerInfo(await Purchases.restorePurchases());

          if (!hasExpectedEntitlement(customerInfo)) {
            return {
              type: "failed",
              error:
                "Restore completed, but no expected entitlement became active.",
            } as const;
          }

          return { type: "restored" } as const;
        } catch (error) {
          return {
            type: "failed",
            error: (error as any)?.message ?? "Restore failed",
          } as const;
        }
      },
    }),
    [],
  );

  return (
    <>
      <MonetizationBootstrap />

      <CustomPurchaseControllerProvider controller={controller}>
        <SuperwallProvider apiKeys={superwallApiKeys}>
          <SuperwallLoading>
            <LoadingState />
          </SuperwallLoading>

          <SuperwallLoaded>
            <SubscriptionSync />
            <AnalyticsBridge />
            {children}
          </SuperwallLoaded>
        </SuperwallProvider>
      </CustomPurchaseControllerProvider>
    </>
  );
}
