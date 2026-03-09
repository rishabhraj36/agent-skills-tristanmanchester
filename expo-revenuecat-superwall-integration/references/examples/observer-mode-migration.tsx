import { useEffect } from "react";
import { Platform } from "react-native";
import Purchases, {
  LOG_LEVEL,
  PURCHASES_ARE_COMPLETED_BY_TYPE,
  STOREKIT_VERSION,
} from "react-native-purchases";

const revenueCatApiKeys = {
  ios: process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY ?? "",
  android: process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY ?? "",
} as const;

let purchasesConfigured = false;

function getPlatformKey(keys: { ios: string; android: string }) {
  return Platform.OS === "ios" ? keys.ios : keys.android;
}

type RevenueCatObserverModeBootstrapProps = {
  appUserId: string | null;
  shouldSyncHistoricalPurchases: boolean;
};

export function RevenueCatObserverModeBootstrap({
  appUserId,
  shouldSyncHistoricalPurchases,
}: RevenueCatObserverModeBootstrapProps) {
  useEffect(() => {
    const apiKey = getPlatformKey(revenueCatApiKeys);

    if (!apiKey || purchasesConfigured) {
      return;
    }

    if (__DEV__) {
      Purchases.setLogLevel(LOG_LEVEL.DEBUG);
    }

    /**
     * Use this only when the app already owns purchase completion.
     * Older docs may still call this observer mode.
     */
    Purchases.configure({
      apiKey,
      purchasesAreCompletedBy: {
        type: PURCHASES_ARE_COMPLETED_BY_TYPE.MY_APP,
        ...(Platform.OS === "ios"
          ? { storeKitVersion: STOREKIT_VERSION.STOREKIT_2 }
          : null),
      },
      ...(appUserId ? { appUserID: appUserId } : null),
    });

    purchasesConfigured = true;
  }, [appUserId]);

  useEffect(() => {
    if (!purchasesConfigured || !appUserId) {
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        await Purchases.logIn(appUserId);

        /**
         * Sync historical purchases only at deliberate checkpoints,
         * usually after login or as part of a migration step.
         */
        if (shouldSyncHistoricalPurchases) {
          await Purchases.syncPurchases();
        }
      } catch (error) {
        if (!cancelled) {
          console.warn("RevenueCat observer-mode login or historical sync failed:", error);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [appUserId, shouldSyncHistoricalPurchases]);

  return null;
}
