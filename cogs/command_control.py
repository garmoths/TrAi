import discord
from discord.ext import commands
from utils import db
from utils.logger import get_logger


logger = get_logger(__name__)


def is_admin_or_owner(ctx):
    try:
        if ctx.author.id == ctx.guild.owner_id:
            return True
        if getattr(ctx.author, "guild_permissions", None) and ctx.author.guild_permissions.administrator:
            return True
    except Exception:
        return False
    return False


def global_check(bot):
    async def _check(ctx: commands.Context):
        # don't interfere with DMs or unknown commands
        if not ctx.guild or not ctx.command:
            return True

        settings = db.kv_get("settings", {}) or {}
        guild_conf = settings.get(str(ctx.guild.id), {})
        commands_conf = guild_conf.get("commands", {})
        cmd_conf = commands_conf.get(ctx.command.name, {})

        if cmd_conf and cmd_conf.get("enabled") is False:
            # allow owner or admins to bypass
            if is_admin_or_owner(ctx):
                return True
            raise commands.CheckFailure("Bu komut sunucu ayarlarında devre dışı bırakılmış.")

        return True

    return _check


class CommandControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # ensure the check is added once
        try:
            self.bot.add_check(global_check(self.bot))
        except Exception:
            logger.exception("Global command check eklenemedi")


async def setup(bot):
    await bot.add_cog(CommandControl(bot))
