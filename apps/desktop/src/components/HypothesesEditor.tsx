import { ActionIcon, Button, Group, Stack, Text, Textarea } from '@mantine/core';
import { IconPlus, IconTrash } from '@tabler/icons-react';

interface Props {
  value: string[];
  onChange: (v: string[]) => void;
  onBlur?: () => void;
  prefix?: string;
}

export function HypothesesEditor({ value, onChange, onBlur, prefix = 'H' }: Props) {
  const items = value.length ? value : [''];
  const update = (i: number, text: string) => onChange(items.map((h, j) => (j === i ? text : h)));
  const remove = (i: number) => onChange(items.filter((_, j) => j !== i));

  return (
    <Stack gap="xs">
      {items.map((h, i) => (
        <Group key={i} align="flex-start" wrap="nowrap" gap="xs">
          <Text fw={600} c="brand.6" w={30} pt={7} size="sm">{prefix}{i + 1}</Text>
          <Textarea
            style={{ flex: 1 }}
            minRows={1}
            placeholder="Ex. : Les étudiants tutorés obtiennent de meilleures notes que les autres."
            value={h}
            onChange={(e) => update(i, e.currentTarget.value)}
            onBlur={onBlur}
            aria-label={`Hypothèse ${i + 1}`}
          />
          <ActionIcon
            variant="subtle"
            color="gray"
            mt={4}
            onClick={() => remove(i)}
            disabled={items.length === 1 && !items[0]}
            aria-label={`Supprimer l'hypothèse ${i + 1}`}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ))}
      <Group>
        <Button variant="subtle" size="xs" leftSection={<IconPlus size={14} />}
          onClick={() => onChange([...items, ''])} disabled={items.length >= 50}>
          Ajouter une hypothèse
        </Button>
      </Group>
    </Stack>
  );
}
