import Purchases from "react-native-purchases";

type OnPurchaseParams = {
  productId: string;
  basePlanId?: string;
  offerId?: string;
};

function getPlayOptionId(basePlanId?: string, offerId?: string) {
  return [basePlanId, offerId].filter(Boolean).join(":");
}

function resolvePlaySubscriptionOption(
  storeProduct: any,
  basePlanId?: string,
  offerId?: string,
) {
  const optionId = getPlayOptionId(basePlanId, offerId);
  const options: any[] = Array.isArray(storeProduct?.subscriptionOptions)
    ? storeProduct.subscriptionOptions
    : [];

  if (optionId) {
    const explicit = options.find((option) => option?.id === optionId);

    if (explicit) {
      return explicit;
    }
  }

  return storeProduct?.defaultOption ?? options[0] ?? null;
}

export async function purchaseFromSuperwallParams({
  productId,
  basePlanId,
  offerId,
}: OnPurchaseParams) {
  const [storeProduct] = await Purchases.getProducts([productId]);

  if (!storeProduct) {
    throw new Error(`No RevenueCat product found for ${productId}`);
  }

  const option = resolvePlaySubscriptionOption(
    storeProduct,
    basePlanId,
    offerId,
  );

  if (!option) {
    throw new Error(
      `No Google Play subscription option matched ${getPlayOptionId(
        basePlanId,
        offerId,
      ) || "the default selection"}`,
    );
  }

  /**
   * Adapt this call to the exact purchase helper exposed by the installed
   * `react-native-purchases` version.
   */
  const purchasesModule: any = Purchases as any;

  if (typeof purchasesModule.purchaseSubscriptionOption === "function") {
    return await purchasesModule.purchaseSubscriptionOption(option);
  }

  if (typeof purchasesModule.purchase === "function") {
    return await purchasesModule.purchase({
      storeProduct,
      subscriptionOption: option,
    });
  }

  return await purchasesModule.purchaseStoreProduct(storeProduct);
}
