from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.lexicon.lexicon import LEXICON_MSG
from app.keyboards.privacy_keyboard import get_privacy_keyboard
from app.states import LoginState
from app.handlers.login import login_command

privacy_router = Router()


@privacy_router.callback_query(F.data == "start_login")
async def show_privacy_policy(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()

    await callback.message.answer(
        LEXICON_MSG["privacy_policy_required"]["en"],
        reply_markup=get_privacy_keyboard("en"),
    )


@privacy_router.callback_query(F.data == "accept_privacy")
async def accept_privacy(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()

    await state.update_data(privacy_accepted=True)
    await state.set_state(LoginState.waiting_for_privacy)

    await login_command(callback.message, state, "en")
    await callback.answer()


@privacy_router.callback_query(F.data == "decline_privacy")
async def decline_privacy(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.update_data(privacy_accepted=False)
    await callback.message.answer(LEXICON_MSG["privacy_policy_declined"]["en"])
    await callback.answer()
