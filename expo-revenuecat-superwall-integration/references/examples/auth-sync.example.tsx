import { useEffect, useRef } from "react";
import Purchases from "react-native-purchases";
import { useUser } from "expo-superwall";

type AuthIdentitySyncProps = {
  /**
   * Set to true once the app knows whether a user session exists.
   */
  isAuthResolved: boolean;

  /**
   * The stable billing user ID. Prefer a UUID or another opaque backend ID.
   */
  userId: string | null;

  /**
   * True only if the product genuinely supports guest mode after sign out.
   * If false, the hook avoids `Purchases.logOut()` so the SDK never creates
   * a fresh anonymous user during account switching.
   */
  allowAnonymousState: boolean;
};

export function AuthIdentitySync({
  isAuthResolved,
  userId,
  allowAnonymousState,
}: AuthIdentitySyncProps) {
  const { identify, signOut } = useUser();
  const lastAppliedUserId = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    if (!isAuthResolved) {
      return;
    }

    if (lastAppliedUserId.current === userId) {
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        if (userId) {
          await Purchases.logIn(userId);

          if (!cancelled) {
            await identify(userId);
          }
        } else if (allowAnonymousState) {
          await Purchases.logOut();

          if (!cancelled) {
            await signOut();
          }
        } else {
          /**
           * Login-required or custom-ID-only products should not create a fresh
           * anonymous RevenueCat user on logout. Let the app remain in a signed-out
           * app state and wait until the next real user logs in.
           */
        }

        lastAppliedUserId.current = userId;
      } catch (error) {
        console.error("Failed to sync billing identity:", error);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [allowAnonymousState, identify, isAuthResolved, signOut, userId]);

  return null;
}
