class Execute:
    def __init__(self, memory, registers, alu):
        self.memory = memory
        self.registers = registers
        self.alu = alu

    # Stage 3: Execute (EX) - With Hazard Detection and Forwarding
    def execute(self, ID_EX, EX_MEM, MEM_WB):
        inst_type = ID_EX['inst_type']
        fields = ID_EX['fields']
        
        # Initialize forwarding values and detection flags
        src_value, temp_value = None, None
        needs_forwarding_src, needs_forwarding_temp = False, False

        # Check for data hazards and forward if necessary
        if inst_type == RtypeInst or inst_type == ItypeInst:
            src_reg = int(fields.rs, 2)
            temp_reg = int(fields.rt, 2) if inst_type == RtypeInst else None

            # Forward from EX/MEM if EX_MEM has the destination register
            if EX_MEM['dest_reg'] is not None and EX_MEM['dest_reg'] == src_reg:
                src_value = EX_MEM['ALU_result']
                needs_forwarding_src = True
            elif MEM_WB['dest_reg'] is not None and MEM_WB['dest_reg'] == src_reg:
                src_value = MEM_WB['ALU_result'] if MEM_WB['inst_type'] != "load" else MEM_WB['mem_data']
                needs_forwarding_src = True

            if temp_reg is not None:
                if EX_MEM['dest_reg'] is not None and EX_MEM['dest_reg'] == temp_reg:
                    temp_value = EX_MEM['ALU_result']
                    needs_forwarding_temp = True
                elif MEM_WB['dest_reg'] is not None and MEM_WB['dest_reg'] == temp_reg:
                    temp_value = MEM_WB['ALU_result'] if MEM_WB['inst_type'] != "load" else MEM_WB['mem_data']
                    needs_forwarding_temp = True

            # If no forwarding was needed, read from the register file
            if not needs_forwarding_src:
                src_value = self.registers.read(src_reg)
            if temp_reg is not None and not needs_forwarding_temp:
                temp_value = self.registers.read(temp_reg)

        # Execute based on instruction type
        match inst_type:
            case RtypeInst:
                # Handle R-type instruction
                if fields.funct == "001000":  # `jr` instruction
                    EX_MEM['PC'] = src_value
                elif fields.funct.startswith("000"):
                    EX_MEM['ALU_result'] = self.alu.alu_shift(fields.funct, src_value, fields.shamt)
                else:
                    EX_MEM['ALU_result'] = self.alu.alu_arith(fields.funct, src_value, temp_value)
                
                EX_MEM['dest_reg'] = int(fields.rd, 2)
                EX_MEM['inst_type'] = inst_type

            case JtypeInst:
                # Handle J-type instruction (j, jal)
                addr = int(fields.address, 2)
                if int(fields.op[3:], 2) == 2:  # jump
                    EX_MEM['PC'] = (ID_EX['PC'] & 0xF0000000) | (addr << 2)
                else:  # jump and link
                    self.registers.write(31, ID_EX['PC'] + 4)  # write return address
                    EX_MEM['PC'] = (ID_EX['PC'] & 0xF0000000) | (addr << 2)

            case ItypeInst:
                # Handle I-type instruction (load/store, branch, immediate arithmetic)
                match fields.op[0:3]:
                    case "100":  # Load instruction
                        addr = int(self.alu.giveAddr(fields.rs, fields.addrORimm), 2)
                        EX_MEM['mem_addr'] = addr
                        EX_MEM['dest_reg'] = int(fields.rt, 2)
                        EX_MEM['inst_type'] = "load"

                    case "101":  # Store instruction
                        addr = int(self.alu.giveAddr(fields.rs, fields.addrORimm), 2)
                        EX_MEM['mem_addr'] = addr
                        EX_MEM['src_data'] = src_value if needs_forwarding_src else self.registers.read(int(fields.rt, 2))
                        EX_MEM['inst_type'] = "store"

                    case "001":  # Immediate arithmetic
                        EX_MEM['ALU_result'] = self.alu.alu_arith_i(fields.op[3:6], src_value, fields.addrORimm)
                        EX_MEM['dest_reg'] = int(fields.rt, 2)
                        EX_MEM['inst_type'] = "arith_i"

                    case "000":  # Branching (beq, bne)
                        dst_val = temp_value if needs_forwarding_temp else self.registers.read(int(fields.rt, 2))
                        imm = int(fields.addrORimm, 2)
                        if imm & 0x8000:  # sign-extend if negative
                            imm |= 0xFFFF0000
                        equal = self.alu.isEqual(src_value, dst_val)
                        branch_condition = int(fields.op[3:], 2) == 4  # beq if 4, bne otherwise
                        if equal == branch_condition:
                            EX_MEM['PC'] = ID_EX['PC'] + 4 + (imm << 2)
                        EX_MEM['inst_type'] = "branch"
