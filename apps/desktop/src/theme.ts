import { createTheme, type MantineColorsTuple } from '@mantine/core';

// Bleu profond « académique », lisible et sobre.
const brand: MantineColorsTuple = [
  '#eef3ff', '#dce4f5', '#b6c6ea', '#8da6df', '#6b8bd5', '#557acf',
  '#4971cd', '#3a60b5', '#3155a3', '#244891',
];

export const theme = createTheme({
  primaryColor: 'brand',
  colors: { brand },
  fontFamily: "'Inter Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
  headings: { fontFamily: "'Inter Variable', system-ui, sans-serif", fontWeight: '650' },
  defaultRadius: 'md',
  cursorType: 'pointer',
  components: {
    Button: { defaultProps: { radius: 'md' } },
    Paper: { defaultProps: { radius: 'lg' } },
    Card: { defaultProps: { radius: 'lg' } },
    Textarea: { defaultProps: { autosize: true, minRows: 2, maxRows: 10 } },
  },
});
