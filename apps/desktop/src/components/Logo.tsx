import { Group, Text, ThemeIcon } from '@mantine/core';
import { IconChartDots3 } from '@tabler/icons-react';

export function Logo({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const big = size === 'lg';
  return (
    <Group gap={big ? 'sm' : 8} wrap="nowrap">
      <ThemeIcon
        size={big ? 44 : 30}
        radius="md"
        variant="gradient"
        gradient={{ from: 'brand.7', to: 'teal.6', deg: 135 }}
      >
        <IconChartDots3 size={big ? 26 : 18} stroke={1.8} />
      </ThemeIcon>
      <Text fw={750} fz={big ? 28 : 18} lts={-0.3}>
        STAT<Text span inherit c="brand.6">PFE</Text>
      </Text>
    </Group>
  );
}
