import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { casePresets, type CasePreset } from '../data/casePresets';
import type { ImportResult } from '../types';

/** 按 period 隔离的 hub 数据摘要(从 erp_samples loader 拉到的元数据)。 */
export interface HubSummary {
  salesCount: number;
  purchasesCount: number;
  cancelledCount: number;
  amendsCount: number;
  lastPulledAt: string | null;
}

/**
 * Working Buffer — 当前用户正在处理的 case 的完整快照。
 *
 * 生命周期:
 *   - 从 Dashboard 选 case 开始填充(loadCase)
 *   - 跨页面共享(Preview / Agent / NewFiling 都从它读)
 *   - 切换 case 时被覆盖(不 stack)
 *   - 按"清空数据"按钮后清空(clearBuffer / clearAll)
 *   - persist 到 localStorage,key = 'taxi:demo-buffer',刷新页面会还原
 *
 * 不变量(代码 review 时核对):
 *   1. buffer !== null ⇒ buffer.preset 必填
 *   2. buffer.nineBox keys ⊆ 7 个 box category(见下)
 *   3. buffer.erpData 可能为 null,即使 buffer 存在
 *   4. selectedPreset === buffer.presetId(同步维护,PR 5 才删 selectedPreset)
 *
 * 字段名映射(VAT 9-Box):
 *   Box 1: vat_due_sales
 *   Box 2: vat_due_acquisitions
 *   Box 3: (空,恒 0)
 *   Box 4: vat_reclaimed_purchases
 *   Box 5: (后端算,不在 buffer 里)
 *   Box 6: total_sales_ex_vat
 *   Box 7: total_purchases_ex_vat
 *   Box 8: total_goods_supplied_eu
 *   Box 9: total_goods_acquired_eu
 */
export interface CaseWorkingBuffer {
  presetId: string;
  preset: CasePreset;
  erpData: ImportResult | null;
  nineBox: Record<string, number>;
  loadedAt: string;
  lastEditedAt: string;
}

interface DemoState {
  // ── 现状字段(PR 1 保留,PR 5 才删) ──
  /** @deprecated 改读 buffer.presetId。本字段在 PR 1 仍由 loadCase/clearAll 同步维护,保证零行为变更。 */
  selectedPreset: string | null;
  erpConnectionOn: boolean;

  // ── 新增:ERPNext 连接状态(Phase 3 C 路径) ──
  erpnextStatus: 'idle' | 'connected' | 'disconnected' | 'error';
  erpnextLastPushAt: string | null;
  erpnextSalesCount: number;
  erpnextPurchasesCount: number;
  erpnextDocnames: string[];

  // ── 新增:ERPNext 凭证(明文,本期 demo 限制) ──
  erpnextCredentials: {
    url: string;
    apiKey: string;
    apiSecret: string;
  } | null;

  // ── 新增:按 period 隔离的 hub 数据摘要 ──
  hubDataByPeriod: Record<string, HubSummary>;

  // ── 现状 actions(全部保留) ──
  setSelectedPreset: (preset: string | null) => void;
  setErpConnection: (on: boolean) => void;
  clearAll: () => void;
  setErpnextCredentials: (creds: { url: string; apiKey: string; apiSecret: string } | null) => void;
  setHubDataForPeriod: (period: string, summary: HubSummary) => void;

  // ── 新增:working buffer ──
  buffer: CaseWorkingBuffer | null;

  // ── 新增 actions ──
  /** 加载 case 到 buffer(总是覆盖)。从 preset.lineItems 抽 7 个 box 数字作为 nineBox 默认值。 */
  loadCase: (preset: CasePreset) => void;
  /** 单独刷 erpData(不影响 nineBox / lastEditedAt)。仅当 buffer 存在时生效。 */
  setErpData: (data: ImportResult) => void;
  /** 单 box 编辑。更新 nineBox[key] 和 lastEditedAt。仅当 buffer 存在时生效。 */
  setNineBoxValue: (key: string, value: number) => void;
  /** 把 nineBox 回到 preset.lineItems 默认值,更新 lastEditedAt。 */
  resetNineBox: () => void;
  /** 清空 buffer,同步清 selectedPreset,清 localStorage(同 clearAll)。 */
  clearBuffer: () => void;

  // ── 新增 selectors ──
  isCaseLoaded: () => boolean;
  isMatchingCase: (presetId: string) => boolean;

  // ── 新增:ERPNext actions(Phase 3 C 路径) ──
  /** 拉一次 /api/erp/erpnext/status 同步到 store。toggle 开启时由组件起轮询。 */
  refreshErpnextStatus: () => Promise<void>;
}

/**
 * 从 preset.lineItems 抽 7 个数字字段(Box 1/2/4/6/7/8/9)。
 * Box 3 恒 0、Box 5 后端算 — 都不存。
 */
function defaultNineBoxFromPreset(preset: CasePreset): Record<string, number> {
  return Object.fromEntries(preset.lineItems.map((li) => [li.category, li.amount]));
}

/**
 * store 的 default 状态。v1 → v2 迁移时直接 spread,丢掉老 ID。
 * 以后加新字段时,只需要在这里加一次,migrate 不用动。
 */
const DEFAULT_DEMO_STATE = {
  selectedPreset: null,
  erpConnectionOn: false,
  buffer: null,
  erpnextStatus: 'idle' as const,
  erpnextLastPushAt: null,
  erpnextSalesCount: 0,
  erpnextPurchasesCount: 0,
  erpnextDocnames: [] as string[],
  erpnextCredentials: null,
  hubDataByPeriod: {} as Record<string, HubSummary>,
};

export const useDemoStore = create<DemoState>()(
  persist(
    (set, get) => ({
      // ── 现状字段初值 ──
      selectedPreset: null,
      erpConnectionOn: false,

      // ── ERPNext 状态初值 ──
      erpnextStatus: 'idle',
      erpnextLastPushAt: null,
      erpnextSalesCount: 0,
      erpnextPurchasesCount: 0,
      erpnextDocnames: [],

      // ── ERPNext 凭证初值 ──
      erpnextCredentials: null,

      // ── 按 period 隔离的 hub 数据初值 ──
      hubDataByPeriod: {},

      setSelectedPreset: (preset) => set({ selectedPreset: preset }),
      setErpConnection: (on) => set({ erpConnectionOn: on }),
      clearAll: () => {
        set({
          selectedPreset: null,
          erpConnectionOn: false,
          buffer: null,
          // 关闭 ERPNext 状态
          erpnextStatus: 'idle',
          erpnextLastPushAt: null,
          erpnextSalesCount: 0,
          erpnextPurchasesCount: 0,
          erpnextDocnames: [],
          // 清除 ERPNext 凭证
          erpnextCredentials: null,
          // 清除 hub 数据
          hubDataByPeriod: {},
        });
        // 同步清 localStorage(保留现状 ClearDataButton 行为)
        if (typeof window !== 'undefined') {
          try {
            Object.keys(localStorage)
              .filter((k) => k.startsWith('taxi:') || k.startsWith('tax_agent:'))
              .forEach((k) => localStorage.removeItem(k));
          } catch (e) {
            // localStorage 不可用,忽略
          }
        }
      },

      // ── 新增:working buffer ──
      buffer: null,

      loadCase: (preset) => {
        const now = new Date().toISOString();
        set({
          // 同步维护 selectedPreset(零行为变更)
          selectedPreset: preset.id,
          buffer: {
            presetId: preset.id,
            preset,
            erpData: null,
            nineBox: defaultNineBoxFromPreset(preset),
            loadedAt: now,
            lastEditedAt: now,
          },
        });
      },

      setErpData: (data) => {
        const cur = get().buffer;
        if (!cur) return;
        set({ buffer: { ...cur, erpData: data } });
      },

      setNineBoxValue: (key, value) => {
        const cur = get().buffer;
        if (!cur) return;
        set({
          buffer: {
            ...cur,
            nineBox: { ...cur.nineBox, [key]: value },
            lastEditedAt: new Date().toISOString(),
          },
        });
      },

      resetNineBox: () => {
        const cur = get().buffer;
        if (!cur) return;
        set({
          buffer: {
            ...cur,
            nineBox: defaultNineBoxFromPreset(cur.preset),
            lastEditedAt: new Date().toISOString(),
          },
        });
      },

      clearBuffer: () => {
        // 同时清 selectedPreset 保持同步
        set({ selectedPreset: null, buffer: null });
      },

      // ── selectors ──
      isCaseLoaded: () => get().buffer !== null,
      isMatchingCase: (presetId) => get().buffer?.presetId === presetId,

      // ── ERPNext actions(Phase 3 C 路径) ──
      refreshErpnextStatus: async () => {
        try {
          const { getErpNextStatus } = await import('../api/erpnext');
          const data = await getErpNextStatus();
          set({
            erpnextStatus: data.connected ? 'connected' : 'disconnected',
            erpnextLastPushAt: data.last_push_at,
            erpnextSalesCount: data.sales_count,
            erpnextPurchasesCount: data.purchases_count,
            erpnextDocnames: data.docnames,
          });
        } catch (e) {
          set({ erpnextStatus: 'error' });
        }
      },

      // ── ERPNext 凭证 actions(Import Hub) ──
      setErpnextCredentials: (creds) => set({ erpnextCredentials: creds }),

      // ── Hub 数据 actions(按 period 隔离) ──
      setHubDataForPeriod: (period, summary) =>
        set((state) => ({
          hubDataByPeriod: { ...state.hubDataByPeriod, [period]: summary },
        })),
    }),
    {
      name: 'taxi:demo-buffer',
      version: 3,
      storage: createJSONStorage(() => localStorage),
      // 持久化 buffer + selectedPreset(同步)+ erpConnectionOn
      // action 函数不持久化
      partialize: (state) => ({
        buffer: state.buffer,
        selectedPreset: state.selectedPreset,
        erpConnectionOn: state.erpConnectionOn,
        erpnextCredentials: state.erpnextCredentials,
        hubDataByPeriod: state.hubDataByPeriod,
      }),
      // 持久化版本升级时:
      //   v1 → v2:case 精简后 preset ID 改名,旧 buffer.preset.id 失效,直接 discard
      //   v2 → v3:补全新增的 erpnextCredentials / hubDataByPeriod 字段(老数据里没有)
      migrate: (persistedState, version) => {
        if (version < 2) {
          // 旧 ID 全部 discard(standard-taxable / real-business-q1 / net-refund / zero-filing)
          return { ...DEFAULT_DEMO_STATE } as any;
        }
        if (version < 3) {
          // 补默认值
          return {
            ...(persistedState as any),
            erpnextCredentials: (persistedState as any).erpnextCredentials ?? null,
            hubDataByPeriod: (persistedState as any).hubDataByPeriod ?? {},
          };
        }
        return persistedState as any;
      },
      // 重水化后:若 buffer 存在但 selectedPreset 缺失(老数据/手动改),补齐
      // 还要校验 buffer.preset.id 是否是当前 casePresets 里的有效 ID
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        if (state.buffer && !state.selectedPreset) {
          state.selectedPreset = state.buffer.presetId;
        }
        // 防御:若 buffer 指向已废弃的 preset id,清掉
        const validIds = casePresets.map((p) => p.id);
        if (state.buffer && !validIds.includes(state.buffer.presetId)) {
          state.buffer = null;
          state.selectedPreset = null;
        }
      },
    }
  )
);
