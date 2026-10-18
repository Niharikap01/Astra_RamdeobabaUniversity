/**
 * Shared Themed EChart Wrapper
 * Automatically applies NightWatch dark navy tokens, typography, and tooltip styling.
 * Supports echarts.connect grouping for multi-chart linked scrubbers.
 */

import React, { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";
import { TOKENS } from "../styles/tokens";

interface EChartProps {
  option: any;
  style?: React.CSSProperties;
  className?: string;
  onEvents?: Record<string, (params: any) => void>;
  notMerge?: boolean;
  group?: string;
  onChartReady?: (instance: any) => void;
}

export const EChart: React.FC<EChartProps> = ({
  option,
  style,
  className = "",
  onEvents,
  notMerge = true,
  group,
  onChartReady,
}) => {
  const themedOption = useMemo(() => {
    const dark = TOKENS.colors.dark;

    const baseTheme = {
      backgroundColor: "transparent",
      textStyle: {
        fontFamily: TOKENS.typography.fontSans,
        color: dark.textSecondary,
      },
      tooltip: {
        backgroundColor: dark.bgSurfaceElevated,
        borderColor: dark.borderActive,
        textStyle: {
          color: dark.textPrimary,
          fontFamily: TOKENS.typography.fontSans,
          fontSize: 12,
        },
        padding: [8, 12],
        borderWidth: 1,
        extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45); border-radius: 8px;",
      },
    };

    return {
      ...baseTheme,
      ...option,
      textStyle: {
        ...baseTheme.textStyle,
        ...(option.textStyle || {}),
      },
      tooltip: {
        ...baseTheme.tooltip,
        ...(option.tooltip || {}),
      },
    };
  }, [option]);

  const handleChartReady = (instance: any) => {
    if (group && instance) {
      instance.group = group;
      echarts.connect(group);
    }
    if (onChartReady) {
      onChartReady(instance);
    }
  };

  return (
    <div className={`w-full relative ${className}`}>
      <ReactECharts
        option={themedOption}
        style={{ height: "100%", width: "100%", minHeight: "260px", ...style }}
        onEvents={onEvents}
        notMerge={notMerge}
        onChartReady={handleChartReady}
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
};
