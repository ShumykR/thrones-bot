import re

with open('map_omg.svg', 'r', encoding='utf-8') as f:
    svg = f.read()

paths = re.findall(r'<path[^>]*d="([^"]+)"[^>]*>', svg)
print(f'Found {len(paths)} path data strings.')

castles = [
    'Вінтерфелл',
    'Залізні Острови',
    'Ріверран',
    'Орлине Гніздо',
    'Кастерлі Рок',
    'Королівська Гавань',
    'Хайгарден',
    'Штормовий Кінець',
    'Сонячний Спис',
    'Драконячий Камінь'
]

component_code = '''import { motion } from 'framer-motion';

const CASTLE_NAMES = [
'''
for c in castles:
    component_code += f'  "{c}",\n'

component_code += '''];

const PATHS = [
'''
for p in paths:
    component_code += f'  "{p}",\n'

component_code += '''];

export default function MapSvg({ state, onCastleClick, getColorForUser }) {
  // Mapping paths to castles based on index
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 754.18 1821.24" className="westeros-img interactive-svg">
      {PATHS.map((d, index) => {
        const castleName = CASTLE_NAMES[index];
        const castle = state.castles.find(c => c.name === castleName) || { name: castleName };
        const color = getColorForUser(castle.owner?.id);
        
        return (
          <motion.path
            key={index}
            d={d}
            fill={color}
            stroke="#ffffff"
            strokeWidth="2"
            strokeMiterlimit="10"
            whileHover={{ filter: "brightness(1.5)" }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onCastleClick(castle)}
            style={{ cursor: "pointer", transition: "fill 0.3s ease" }}
          />
        );
      })}
    </svg>
  );
}
'''
with open('webapp/src/components/MapSvg.jsx', 'w', encoding='utf-8') as f:
    f.write(component_code)
print('Generated MapSvg.jsx')
