"""
Repository: Equipment e Inventory (equip, unequip, move, add/remove items).
Supporta 12 slot con conflitto due mani (two_hand -> main_hand + blocco off_hand).
"""

from typing import Optional, List, Dict

from ..base_repository import BaseRepository


VALID_SLOTS = [
    'head', 'neck', 'shoulders', 'chest', 'gloves',
    'main_hand', 'off_hand', 'belt', 'ring', 'legs', 'feet', 'back'
]

INVENTORY_CAPACITY = 32


class EquipmentRepository(BaseRepository):
    """Operazioni su equipment, character_equipment e inventory."""

    def get_all_classes(self) -> List[Dict]:
        """Ottieni tutte le classi disponibili."""
        return self.get_all('classes')

    def get_equipment_by_name(self, name: str) -> Optional[Dict]:
        """Trova equipment per nome."""
        equipment = self.get_where('equipment', name=name)
        return equipment[0] if equipment else None

    # ══════════════════════════════════════════════════════
    # TWO-HAND HELPERS
    # ══════════════════════════════════════════════════════

    def _is_two_hand(self, equipment: Dict) -> bool:
        """Controlla se un item e' a due mani."""
        return 'two_hand' in equipment.get('equip_tags', [])

    def _get_main_hand_equipment(self, character_id: str) -> Optional[Dict]:
        """Ottieni l'equipment nel main_hand (con dati completi)."""
        main = self.get_where('character_equipment', character_id=character_id, equipped_slot='main_hand')
        if main:
            return self.get_by_id('equipment', main[0]['equipment_id'])
        return None

    def _clear_slot_to_inventory(self, character_id: str, slot: str):
        """Rimuove item da uno slot e lo mette in inventario."""
        existing = self.get_where('character_equipment', character_id=character_id, equipped_slot=slot)
        for eq in existing:
            old_equipment = self.get_by_id('equipment', eq['equipment_id'])
            if old_equipment:
                self.add_to_inventory(character_id, old_equipment['name'], 1)
            self.delete('character_equipment', eq['id'])

    def get_two_hand_status(self, character_id: str) -> dict:
        """Ritorna lo stato del two-hand lock."""
        main_eq = self._get_main_hand_equipment(character_id)
        if main_eq and self._is_two_hand(main_eq):
            return {'is_two_hand': True, 'item_name': main_eq['name']}
        return {'is_two_hand': False}

    # ══════════════════════════════════════════════════════
    # EQUIP / UNEQUIP / MOVE
    # ══════════════════════════════════════════════════════

    def equip_item(self, character_id: str, equipment_id: str, slot: str) -> Dict:
        """Equipaggia un item in uno slot."""
        self.delete_where('character_equipment', character_id=character_id, equipped_slot=slot)

        return self.insert('character_equipment', {
            'id': self._generate_id('ceq'),
            'character_id': character_id,
            'equipment_id': equipment_id,
            'equipped_slot': slot
        })

    def equip_from_inventory(self, character_id: str, item_name: str, slot: str) -> Optional[Dict]:
        """Equipaggia un item dall'inventario con gestione conflitto due mani."""
        inv_items = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if not inv_items:
            return None

        equipment = self.get_equipment_by_name(item_name)
        if not equipment:
            return None

        equip_tags = equipment.get('equip_tags', [])
        is_two_hand = self._is_two_hand(equipment)

        # ── Validazione slot ──
        if is_two_hand:
            # Item two_hand va sempre in main_hand
            if slot != 'main_hand':
                return None
        elif slot not in equip_tags:
            return None

        # ── Gestione conflitto two-hand ──
        if is_two_hand:
            # Equipaggiare un two_hand: svuota sia main_hand che off_hand
            self._clear_slot_to_inventory(character_id, 'main_hand')
            self._clear_slot_to_inventory(character_id, 'off_hand')
        else:
            # Equipaggiare in main_hand o off_hand: controlla se c'e' un two_hand in main_hand
            if slot in ('main_hand', 'off_hand'):
                main_eq = self._get_main_hand_equipment(character_id)
                if main_eq and self._is_two_hand(main_eq):
                    # Rimuovi il two_hand da main_hand
                    self._clear_slot_to_inventory(character_id, 'main_hand')

            # Svuota lo slot target normalmente
            self._clear_slot_to_inventory(character_id, slot)

        self.remove_from_inventory(character_id, item_name, 1)
        return self.equip_item(character_id, equipment['id'], slot)

    def unequip_to_inventory(self, character_id: str, slot: str) -> Optional[Dict]:
        """Rimuovi equipment dallo slot e metti in inventario."""
        equipped = self.get_where('character_equipment', character_id=character_id, equipped_slot=slot)
        if not equipped:
            return None

        for eq in equipped:
            equipment = self.get_by_id('equipment', eq['equipment_id'])
            if equipment:
                self.add_to_inventory(character_id, equipment['name'], 1)
            self.delete('character_equipment', eq['id'])

        return {'success': True, 'slot': slot}

    def move_equipment(self, character_id: str, from_slot: str, to_slot: str) -> Optional[Dict]:
        """Sposta equipment da uno slot a un altro (se compatibile).
        Gestisce conflitto two-hand anche per move.
        """
        equipped = self.get_where('character_equipment', character_id=character_id, equipped_slot=from_slot)
        if not equipped:
            return None

        eq_record = equipped[0]
        equipment = self.get_by_id('equipment', eq_record['equipment_id'])
        if not equipment:
            return None

        equip_tags = equipment.get('equip_tags', [])
        is_two_hand = self._is_two_hand(equipment)

        # Validazione destinazione
        if is_two_hand:
            if to_slot != 'main_hand':
                return None
        elif to_slot not in equip_tags:
            return None

        # Se spostando verso main_hand/off_hand, controlla conflitto two-hand
        if not is_two_hand and to_slot in ('main_hand', 'off_hand'):
            main_eq = self._get_main_hand_equipment(character_id)
            if main_eq and self._is_two_hand(main_eq) and from_slot != 'main_hand':
                self._clear_slot_to_inventory(character_id, 'main_hand')

        # Svuota slot destinazione
        existing_in_target = self.get_where('character_equipment', character_id=character_id, equipped_slot=to_slot)
        for ex in existing_in_target:
            old_eq = self.get_by_id('equipment', ex['equipment_id'])
            if old_eq:
                self.add_to_inventory(character_id, old_eq['name'], 1)
            self.delete('character_equipment', ex['id'])

        self.update('character_equipment', eq_record['id'], {'equipped_slot': to_slot})

        return {'success': True, 'from_slot': from_slot, 'to_slot': to_slot, 'item': equipment['name']}

    # ══════════════════════════════════════════════════════
    # INVENTORY
    # ══════════════════════════════════════════════════════

    def get_inventory_count(self, character_id: str) -> int:
        """Conta item unici nell'inventario (per capacita')."""
        return len(self.get_where('inventory', character_id=character_id))

    def add_to_inventory(self, character_id: str, item_name: str, quantity: int = 1, metadata: Dict = None) -> Dict:
        """Aggiunge item all'inventario (con check capacita')."""
        existing = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if existing:
            # Stack: stessa entry, incrementa quantita'
            new_qty = existing[0].get('quantity', 0) + quantity
            return self.update('inventory', existing[0]['id'], {'quantity': new_qty})

        # Nuovo item: controlla capacita'
        if self.get_inventory_count(character_id) >= INVENTORY_CAPACITY:
            return {'error': 'inventory_full', 'message': 'Inventario pieno'}

        return self.insert('inventory', {
            'id': self._generate_id('inv'),
            'character_id': character_id,
            'item_name': item_name,
            'quantity': quantity,
            'metadata': metadata or {}
        })

    def remove_from_inventory(self, character_id: str, item_name: str, quantity: int = 1) -> bool:
        """Rimuove item dall'inventario."""
        existing = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if not existing:
            return False

        current_qty = existing[0].get('quantity', 0)
        if quantity >= current_qty:
            return self.delete('inventory', existing[0]['id'])
        else:
            self.update('inventory', existing[0]['id'], {'quantity': current_qty - quantity})
            return True

    # ══════════════════════════════════════════════════════
    # CONSUMABILI
    # ══════════════════════════════════════════════════════

    def use_consumable(self, character_id: str, item_name: str) -> Optional[Dict]:
        """Usa un consumabile dall'inventario. Applica use_effect e rimuove se consumed."""
        inv_items = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if not inv_items:
            return None

        equipment = self.get_equipment_by_name(item_name)
        if not equipment:
            return None

        if equipment.get('category') != 'consumable':
            return None

        use_effect = equipment.get('use_effect')
        if not use_effect:
            return None

        char = self.get_by_id('characters', character_id)
        if not char:
            return None

        result = {'item_name': item_name, 'effect': use_effect, 'changes': {}}
        effect_type = use_effect.get('type')
        value = use_effect.get('value', 0)

        if effect_type == 'heal':
            hp_current = char.get('hp_current', 0)
            hp_max = char.get('hp_max', 100)
            new_hp = min(hp_current + value, hp_max)
            healed = new_hp - hp_current
            self._db.update_character_fields(character_id, {'hp_current': new_hp})
            result['changes'] = {'hp_current': new_hp, 'healed': healed}

        elif effect_type == 'mana_restore':
            mana_current = char.get('mana_current', 0)
            mana_max = char.get('mana_max', 100)
            new_mana = min(mana_current + value, mana_max)
            restored = new_mana - mana_current
            self._db.update_character_fields(character_id, {'mana_current': new_mana})
            result['changes'] = {'mana_current': new_mana, 'restored': restored}

        elif effect_type == 'buff':
            stat = use_effect.get('stat')
            duration = use_effect.get('duration', '1_scene')
            if stat:
                result['changes'] = {'buff': stat, 'value': value, 'duration': duration}

        elif effect_type == 'damage':
            damage_type = use_effect.get('damage_type', 'physical')
            result['changes'] = {'damage': value, 'damage_type': damage_type}

        # Rimuovi consumabile se consumed (default true)
        if equipment.get('consumed', True):
            self.remove_from_inventory(character_id, item_name, 1)

        return result

    # ══════════════════════════════════════════════════════
    # SHOP / VENDOR
    # ══════════════════════════════════════════════════════

    def get_shop_inventory(self, npc_id: str) -> Optional[Dict]:
        """Ottieni inventario del negozio di un NPC."""
        world_seed = self._db._cache.get('world_seed', {})
        npcs = world_seed.get('npcs', {})
        npc = npcs.get(npc_id)
        if not npc or 'shop_inventory' not in npc:
            return None

        items = []
        for entry in npc['shop_inventory']:
            eq = self.get_by_id('equipment', entry['equipment_id'])
            if eq:
                buy_price = int(eq.get('sell_price', 0) * entry.get('price_modifier', 1.0))
                items.append({
                    **eq,
                    'stock': entry.get('stock', -1),
                    'buy_price': max(buy_price, 1)
                })

        sell_modifier = npc.get('buy_price_modifier', 0.5)

        # Pre-calcola prezzi di vendita per tutti gli equipment noti
        sell_prices = {}
        for eq in self.get_all('equipment'):
            base = eq.get('sell_price', 0)
            sell_prices[eq['name']] = max(int(base * sell_modifier), 1)

        return {
            'npc_id': npc_id,
            'npc_name': npc.get('name', npc_id),
            'npc_title': npc.get('title', ''),
            'items': items,
            'sell_modifier': sell_modifier,
            'sell_prices': sell_prices,
        }

    def buy_from_shop(self, character_id: str, npc_id: str, equipment_id: str) -> Optional[Dict]:
        """Compra un item dal negozio di un NPC."""
        shop = self.get_shop_inventory(npc_id)
        if not shop:
            return None

        shop_item = None
        for item in shop['items']:
            if item['id'] == equipment_id:
                shop_item = item
                break

        if not shop_item:
            return None

        # Controlla stock
        if shop_item['stock'] == 0:
            return {'error': 'out_of_stock', 'message': 'Esaurito'}

        price = shop_item['buy_price']
        char = self.get_by_id('characters', character_id)
        if not char:
            return None

        corone = char.get('corone', 0)
        if corone < price:
            return {'error': 'not_enough_corone', 'message': 'Corone insufficienti'}

        # Controlla capacita' inventario
        if self.get_inventory_count(character_id) >= INVENTORY_CAPACITY:
            inv_existing = self.get_where('inventory', character_id=character_id, item_name=shop_item['name'])
            if not inv_existing:
                return {'error': 'inventory_full', 'message': 'Inventario pieno'}

        # Transazione: deduce corone, aggiungi item
        self._db.update_character_fields(character_id, {'corone': corone - price})
        self.add_to_inventory(character_id, shop_item['name'], 1)

        # Diminuisci stock (se non infinito) e persisti su disco
        if shop_item['stock'] > 0:
            world_seed = self._db._cache.get('world_seed', {})
            npc = world_seed.get('npcs', {}).get(npc_id)
            if npc:
                for entry in npc.get('shop_inventory', []):
                    if entry['equipment_id'] == equipment_id:
                        entry['stock'] = max(0, entry['stock'] - 1)
                        break
                self._save('world_seed')

        return {
            'success': True,
            'item_name': shop_item['name'],
            'price': price,
            'corone_remaining': corone - price
        }

    def sell_to_shop(self, character_id: str, npc_id: str, item_name: str) -> Optional[Dict]:
        """Vendi un item a un NPC."""
        world_seed = self._db._cache.get('world_seed', {})
        npc = world_seed.get('npcs', {}).get(npc_id)
        if not npc:
            return None

        sell_modifier = npc.get('buy_price_modifier', 0.5)

        # Verifica che il giocatore ha l'item
        inv_items = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if not inv_items:
            return None

        # Defense-in-depth: non vendere item equipaggiati
        equipment = self.get_equipment_by_name(item_name)
        if equipment:
            equipped = self.get_where(
                'character_equipment',
                character_id=character_id,
                equipment_id=equipment['id'],
            )
            if equipped:
                return {'error': 'item_equipped', 'message': 'Rimuovi prima l\'item equipaggiato'}
        sell_price = int((equipment.get('sell_price', 0) if equipment else 0) * sell_modifier)
        sell_price = max(sell_price, 1)

        char = self.get_by_id('characters', character_id)
        if not char:
            return None

        # Transazione: rimuovi item, aggiungi corone
        self.remove_from_inventory(character_id, item_name, 1)
        new_corone = char.get('corone', 0) + sell_price
        self._db.update_character_fields(character_id, {'corone': new_corone})

        return {
            'success': True,
            'item_name': item_name,
            'sell_price': sell_price,
            'corone_remaining': new_corone
        }
