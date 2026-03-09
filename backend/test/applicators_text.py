from statisfy_tags import parse_gm_response
result = parse_gm_response('[DMG: 10 fire | target: self | source: test]')
print(f'Actions trovate: {len(result.all_actions)}')
print(f'Prima action: {result.mechanical[0]}')
