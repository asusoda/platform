import { renderHook, waitFor } from "@testing-library/react";
import apiClient from "../components/utils/axios";
import useOrgModules from "./useOrgModules";

jest.mock("../components/utils/axios", () => ({ __esModule: true, default: { get: jest.fn() } }));
jest.mock("../components/auth/AuthContext", () => ({
  useAuth: () => ({ currentOrg: { id: 7, prefix: "ais" } }),
}));

test("hides only the modules the org switched off", async () => {
  apiClient.get.mockResolvedValue({
    data: {
      modules: [
        { name: "points", enabled: false },
        { name: "storefront", enabled: true },
      ],
    },
  });
  const { result } = renderHook(() => useOrgModules());
  await waitFor(() => expect(result.current.isEnabled("points")).toBe(false));
  expect(apiClient.get).toHaveBeenCalledWith("/api/organizations/7/modules");
  expect(result.current.isEnabled("storefront")).toBe(true);
  expect(result.current.isEnabled("calendar")).toBe(true);
  expect(result.current.isEnabled(undefined)).toBe(true);
});

test("shows every module when the request fails", async () => {
  apiClient.get.mockRejectedValue(new Error("down"));
  const { result } = renderHook(() => useOrgModules());
  await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
  expect(result.current.isEnabled("points")).toBe(true);
});
